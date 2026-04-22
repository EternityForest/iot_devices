"""Matter Controller and Device implementation for python-matter-server."""

from __future__ import annotations

import asyncio
import threading
import time
import traceback
from typing import Any

import aiohttp
from iot_devices.device import Device

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

        self.string_data_point(
            "admin.remove_device",
            handler=self.delete_device_handler,
            description="Delete a device from the matter server by it's device name or by node ID",
        )

        # Device tracking
        self.devices_by_node_id: dict[int, matter_device.MatterDevice] = {}
        self.nodes_by_id: dict[int, Any] = {}  # Raw node objects
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

                evt = asyncio.Event()

                # Start listening task
                listen_task = asyncio.create_task(
                    client.start_listening(init_ready=evt)
                )

                await evt.wait()

                # Discover existing nodes
                await self.discover_nodes()

                # Subscribe to attribute updates for all discovered nodes
                await self.subscribe_to_attributes()

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
                    await self.create_matter_device(node.node_id, node)
        except Exception:
            self.handle_error(f"Discovery failed:\n{traceback.format_exc()}")

    async def subscribe_to_attributes(self):
        """Subscribe to OnOff attribute updates for all nodes.

        Creates individual subscriptions with closures for node_id/endpoint_id
        identification.
        """
        if not self.client:
            return

        try:
            nodes = self.client.get_nodes()

            for node in nodes:
                await self._subscribe_node_attributes(node)

        except Exception:
            self.handle_error(
                f"Failed to subscribe to attributes:\n" f"{traceback.format_exc()}"
            )

    async def _subscribe_node_attributes(self, node: Any) -> None:
        """Subscribe to OnOff updates for a single node.

        Args:
            node: MatterNode object
        """
        if not self.client:
            return

        try:
            node_id = node.node_id
            endpoints = node.endpoints if hasattr(node, "endpoints") else {}

            for endpoint_id, endpoint_data in endpoints.items():
                clusters = getattr(endpoint_data, "clusters", {})
                if not clusters and isinstance(endpoint_data, dict):
                    clusters = endpoint_data.get("clusters", {})

                # Subscribe to OnOff cluster (0x0006) OnOff attribute (0x0000)
                if 0x0006 in clusters:
                    # Create closure to capture node_id and endpoint_id
                    def make_handler(n_id, ep_id):
                        def handler(_type, value):
                            self._on_onoff_update(n_id, ep_id, value)

                        return handler

                    topic = f"{endpoint_id}/6/0"
                    handler = make_handler(node_id, endpoint_id)
                    self.client.subscribe_events(
                        handler, EventType.ATTRIBUTE_UPDATED, node_id, topic
                    )

                    self.print(
                        f"Subscribed to OnOff node={node_id} " f"endpoint={endpoint_id}"
                    )

        except Exception:
            self.handle_error(
                f"Failed to subscribe node {node.node_id} attributes:\n"
                f"{traceback.format_exc()}"
            )

    async def create_matter_device(self, node_id: int, node: Any) -> None:
        """Create a MatterDevice subdevice for a node.

        Args:
            node_id: The Matter node ID
            node: MatterNode object from server
        """
        try:
            # Store raw node object for subdevice access
            self.nodes_by_id[node_id] = node

            # Extract device name from node.device_info
            name = self._get_node_name(node)

            # Create subdevice (host will handle threading)
            # Subdevice can access raw node via parent
            device = self.create_subdevice(
                matter_device.MatterDevice,
                name,
                {"node_id": node_id},
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

    def _on_onoff_update(self, node_id: int, endpoint_id: int, value: Any) -> None:
        """Handle OnOff attribute update from Matter server.

        Args:
            node_id: Matter node ID
            endpoint_id: Endpoint ID
            value: New OnOff value (bool)
        """
        try:
            if node_id not in self.devices_by_node_id:
                return

            device = self.devices_by_node_id[node_id]

            # Only update if this is the correct endpoint
            if device.endpoint_id == endpoint_id:
                device.set_data_point("on", 1 if value else 0, annotation="from_matter")
        except Exception:
            self.handle_exception()

    def _get_node_name(self, node: Any) -> str:
        """Extract friendly name from node.device_info.

        Tries to get node_label, product_name, or product_id.
        Falls back to node_id.

        Args:
            node: MatterNode object

        Returns:
            Friendly device name or fallback
        """
        try:
            device_info = getattr(node, "device_info", {})
            if isinstance(device_info, dict):
                # Try node_label first
                if device_info.get("node_label"):
                    return device_info["node_label"]

                # Try product_name
                if device_info.get("product_name"):
                    return device_info["product_name"]

                # Try product_id
                if device_info.get("product_id"):
                    return f"product_{device_info['product_id']}"
        except Exception:
            self.print(f"Error extracting node name: {traceback.format_exc()}")

        # Fallback to node ID
        node_id = getattr(node, "node_id", "unknown")
        return f"node_{node_id}"

    def on_matter_event(self, event_type: EventType, arg: Any) -> None:
        """Handle Matter server node lifecycle events.

        Responds to node_added and node_removed events to manage subdevices.
        Attribute updates are handled via individual subscriptions with closures.
        """
        try:
            if event_type.value == "node_added":
                # New device commissioned - create subdevice and subscribe
                node_id = arg.get("node_id")
                node = arg.get("node")

                if node_id and node and node_id not in self.devices_by_node_id:
                    asyncio.create_task(self.create_matter_device(node_id, node))
                    # Subscribe to its attributes after creation
                    asyncio.create_task(self._subscribe_node_attributes(node))

            elif event_type.value == "node_removed":
                # Device removed
                node_id = arg.get("node_id")
                if node_id in self.devices_by_node_id:
                    device = self.devices_by_node_id[node_id]
                    self.close_subdevice(device.name)
                    del self.devices_by_node_id[node_id]
                if node_id in self.nodes_by_id:
                    del self.nodes_by_id[node_id]

        except Exception:
            self.handle_exception()

    def commission_handler(self, code: str, timestamp: float, annotation: str) -> None:
        if code and code.strip():
            self.run_coroutine(self.commission_device(code.strip()))
            self.set_data_point("admin.commission_with_code", "")

    def net_commission_handler(
        self, code: str, timestamp: float, annotation: str
    ) -> None:
        if code and code.strip():
            self.run_coroutine(self.commission_device(code.strip(), True))
            self.set_data_point("admin.on_network_commission_with_code", "")

    def delete_device_handler(
        self, code: str, timestamp: float, annotation: str
    ) -> None:
        if code and code.strip():
            self.run_coroutine(self.remove_matter_device(code.strip()))
            self.set_data_point("admin.remove_device", "")

    async def remove_matter_device(self, subdev_name: str):
        if subdev_name.isnumeric():
            num = int(subdev_name)
        else:
            subdev_name = subdev_name.split("/")[-1]
            d: matter_device.MatterDevice = self.subdevices[subdev_name]  # type: ignore
            num = d.node_id
        cl = self.client
        if not cl:
            self.handle_error("No client")
            return
        await cl.remove_node(num)
        self.print(f"Deleted node {num}")

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

            if code.isnumeric():
                result = await self.client.commission_with_code(
                    code, network_only=on_network
                )
            else:
                result = await self.client.commission_on_network(int(code))
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
