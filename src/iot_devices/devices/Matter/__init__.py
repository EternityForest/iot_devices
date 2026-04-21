"""Matter Controller and Device implementation for python-matter-server."""

from __future__ import annotations

import asyncio
import threading
import time
import traceback
from typing import Any

import aiohttp
from iot_devices.device import Device

from chip.clusters import Objects as Clusters
from matter_server.client.client import MatterClient
from matter_server.common.models import EventType
from . import matter_device


class MatterController(Device):
    """Main device managing connections to python-matter-server."""

    device_type = "MatterController"
    readme = """
    Matter protocol device controller using python-matter-server.
    Requires an external Matter server to be running and accessible
    at the configured server_url.

    Features:
    - Auto-discover all commissioned Matter devices
    - Commission new devices via admin.commission_with_code datapoint
    - OnOff cluster support for light/switch control
    - Auto-reconnection with exponential backoff

    Note: Users must configure the Matter server separately.
    """

    config_schema = {
        "type": "object",
        "properties": {
            "server_url": {
                "type": "string",
                "default": "ws://localhost:5580/ws",
                "description": (
                    "WebSocket URL of python-matter-server "
                    "(default: ws://localhost:5580/ws)"
                ),
            }
        },
    }

    def __init__(self, config: dict[str, Any], **kw: Any):
        super().__init__(config, **kw)

        # Datapoints
        self.numeric_data_point("connected", subtype="bool", writable=False)
        self.string_data_point(
            "admin.commission_with_code",
            handler=self.commission_handler,
            description="Commission new device with QR code or setup code",
        )

        self.string_data_point(
            "admin.on_network_commission_with_code",
            handler=self.net_commission_handler,
            description="Commission new device that is already on network",
        )

        # Device tracking
        self.devices_by_node_id: dict[int, matter_device.MatterDevice] = {}
        self.client: MatterClient | None = None

        # LazyMesh pattern: separate async event loop in daemon thread
        self.loop = asyncio.new_event_loop()
        self.should_run = True

        # Start event loop in daemon thread
        self.thread = threading.Thread(
            target=self.loop.run_forever,
            daemon=True,
            name="MatterController:" + self.name,
        )
        self.thread.start()

        # Start main connection task
        asyncio.run_coroutine_threadsafe(self.main_loop(), self.loop)

    def run_coroutine(self, coro):
        """Execute coroutine in the device's event loop.

        This allows subdevices and handlers running in the main thread
        to schedule work in the asyncio event loop.
        """
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    async def main_loop(self):
        """Main connection loop with auto-reconnect and exponential backoff."""
        retry_delay = 10
        max_retry_delay = 300

        while self.should_run:
            try:
                await self.connect_and_listen()
            except Exception:
                self.handle_error(f"Connection failed:\n{traceback.format_exc()}")
                self.set_data_point("connected", 0)

                # Exponential backoff
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 1.5, max_retry_delay)
            else:
                # Successful connection, reset delay
                retry_delay = 10

    async def connect_and_listen(self):
        """Establish connection to Matter server and listen for events."""
        async with aiohttp.ClientSession() as session:
            async with MatterClient(self.config["server_url"], session) as client:
                self.client = client
                # Subscribe to events BEFORE starting listening
                client.subscribe_events(self.on_matter_event)

                evt = asyncio.Event()

                # Start listening task
                listen_task = asyncio.create_task(
                    client.start_listening(init_ready=evt)
                )

                await evt.wait()

                # Discover existing nodes
                await self.discover_nodes()

                self.print("Connected to Matter server")

                self.set_data_point(
                    "connected", 1 if client.connection.connected else 0
                )

                # Wait for disconnect
                try:
                    await listen_task
                except Exception:
                    self.handle_error(f"Listening failed:\n{traceback.format_exc()}")
                    raise

    async def discover_nodes(self):
        """Discover all commissioned Matter nodes and create subdevices."""
        if not self.client:
            return

        try:
            nodes = self.client.get_nodes()

            for node in nodes:
                if node.node_id not in self.devices_by_node_id:
                    await self.create_matter_device(node.node_id, node.device_info)
        except Exception:
            self.handle_error(f"Discovery failed:\n{traceback.format_exc()}")

    async def create_matter_device(
        self, node_id: int, node_data: Clusters.BasicInformation
    ) -> None:
        """Create a MatterDevice subdevice for a node.

        Args:
            node_id: The Matter node ID
            node_data: Node information from server
        """
        try:
            # Extract device name from node attributes
            name = await self.get_node_name(node_id, node_data)

            # Create subdevice (host will handle threading)
            device = self.create_subdevice(
                matter_device.MatterDevice, name, {"node_id": node_id}
            )
            device.wait_ready()

            device.set_parent_controller(self)
            self.devices_by_node_id[node_id] = device

            self.print(f"Created device: {name} (node_id={node_id})")
        except Exception:
            self.handle_error(
                f"Failed to create device for node {node_id}:\n"
                f"{traceback.format_exc()}"
            )

    async def get_node_name(
        self,
        node_id: int,
        node_data: Clusters.BasicInformation | Clusters.BridgedDeviceBasicInformation,
    ) -> str:
        """Extract friendly name from node attributes.

        Tries to get NodeLabel or ProductName from Basic Information
        cluster (0x0028), falls back to node_id.

        Args:
            node_id: The node ID
            node_data: Node information dict

        Returns:
            Friendly device name or fallback
        """
        try:
            # node_data structure: endpoints -> endpoint_id -> clusters
            # -> cluster_id -> attributes -> attribute_id
            for endpoint in node_data.get("endpoints", {}).values():
                clusters = endpoint.get("clusters", {})

                # Basic Information cluster (0x0028)
                if 0x0028 in clusters:
                    attrs = clusters[0x0028].get("attributes", {})

                    # Try NodeLabel (0x0005)
                    if 0x0005 in attrs and attrs[0x0005]:
                        name = attrs[0x0005]
                        if isinstance(name, str):
                            return name

                    # Try ProductName (0x0003)
                    if 0x0003 in attrs and attrs[0x0003]:
                        name = attrs[0x0003]
                        if isinstance(name, str):
                            return name
        except Exception:
            self.print(f"Error extracting node name: {traceback.format_exc()}")

        # Fallback to node ID
        return f"node_{node_id}"

    def on_matter_event(self, event_type: EventType, arg: Any) -> None:
        """Handle Matter server events.

        Routes events to appropriate subdevices or creates new ones
        when devices are commissioned
        """
        try:
            if event_type == "node_added":
                # New device commissioned - create subdevice
                node_id = arg.get("node_id")
                node_data = arg.get("node", {})

                if node_id and node_id not in self.devices_by_node_id:
                    asyncio.create_task(self.create_matter_device(node_id, node_data))

            elif event_type == "node_removed":
                # Device removed
                node_id = arg.get("node_id")
                if node_id in self.devices_by_node_id:
                    device = self.devices_by_node_id[node_id]
                    self.close_subdevice(device.name)
                    del self.devices_by_node_id[node_id]

            elif event_type == "attribute_updated":
                # Route attribute update to appropriate subdevice
                node_id = arg.get("node_id")
                if node_id in self.devices_by_node_id:
                    self.devices_by_node_id[node_id].on_matter_attribute(arg)

        except Exception:
            self.handle_exception()

    def commission_handler(self, code: str, timestamp: float, annotation: str) -> None:
        if code and code.strip():
            self.run_coroutine(self.commission_device(code.strip()))

    def net_commission_handler(
        self, code: str, timestamp: float, annotation: str
    ) -> None:
        if code and code.strip():
            self.run_coroutine(self.commission_device(code.strip(), True))

    async def commission_device(self, code: str, on_network=False) -> None:
        """Commission a new Matter device.

        Args:
            code: QR code or setup code
        """
        if not self.client:
            self.handle_error("Not connected to Matter server")
            return

        try:
            self.print(f"Starting commissioning with code: {code[:10]}...")
            result = await self.client.commission_with_code(
                code, network_only=on_network
            )
            self.print(f"Commissioned ID {result.node_id}!")
        except Exception:
            self.handle_error(f"Commission failed:\n{traceback.format_exc()}")

    def on_before_close(self):
        """Cleanup when device closes."""
        self.should_run = False

        try:
            if self.client:
                self.run_coroutine(self.client.disconnect())
        except Exception:
            self.handle_exception()

        # Stop the event loop
        if self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)

        # Wait briefly for clean shutdown
        time.sleep(0.1)

        return super().close()
