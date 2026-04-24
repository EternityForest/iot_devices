from __future__ import annotations

import traceback
from typing import Any

from scullery.ratelimits import RateLimiter

from iot_devices.device import Device
from chip.clusters import Objects as clusters

from .. import Matter


class MatterDevice(Device):
    """Represents a single Matter node with its clusters and endpoints."""

    device_type = "MatterDevice"

    config_schema = {
        "type": "object",
        "properties": {
            "node_id": {
                "type": "integer",
                "description": "Matter node ID",
            },
        },
    }

    def __init__(self, config: dict[str, Any], **kw: Any):
        super().__init__(config, **kw)

        self.eeprom_ratelimiter = RateLimiter(1 / 60, burst=100)

        self.node_id = config["node_id"]
        self.parent_controller: Matter.MatterController | None = self.get_parent(
            Matter.MatterController
        )

        # Get raw node from parent controller
        node = None
        if self.parent_controller:
            node = self.parent_controller.nodes_by_id.get(self.node_id)

        # Discover endpoint with OnOff cluster (0x0006)
        endpoints = node.endpoints if node and hasattr(node, "endpoints") else {}
        endpoint_id = self._find_onoff_endpoint(endpoints)

        if endpoint_id is None:
            self.handle_error("No endpoint with OnOff cluster found")
            endpoint_id = 1  # Fallback

        self.endpoint_id: int = endpoint_id

        # OnOff cluster support
        self.numeric_data_point(
            "on",
            min=0,
            max=1,
            subtype="bool",
            handler=self.on_handler,
            description="OnOff cluster state",
        )

    def _find_onoff_endpoint(self, endpoints: dict) -> int | None:
        """Find first endpoint with OnOff cluster.

        Args:
            endpoints: Endpoints dict {endpoint_id: MatterEndpoint, ...}

        Returns:
            Endpoint ID with OnOff cluster, or None if not found
        """
        try:
            for endpoint_id, endpoint_data in endpoints.items():
                # endpoint_data is either a MatterEndpoint object or dict
                clusters = getattr(endpoint_data, "clusters", {})
                if not clusters and isinstance(endpoint_data, dict):
                    clusters = endpoint_data.get("clusters", {})

                # OnOff cluster ID is 0x0006
                if 0x0006 in clusters:
                    return endpoint_id

            # If no OnOff found, return first endpoint (usually 0)
            if endpoints:
                return min(endpoints.keys())

        except Exception:
            self.print(f"Error discovering endpoint: {traceback.format_exc()}")

        return None

    def set_parent_controller(self, parent: Matter.MatterController) -> None:
        """Set reference to parent MatterController.

        Args:
            parent: The parent MatterController device
        """
        self.parent_controller = parent

    def on_handler(self, value: float, timestamp: float, annotation: str) -> None:
        """Handle changes to 'on' datapoint.

        Args:
            value: New value (0 or 1)
            timestamp: When value was set
            annotation: Source annotation
        """
        # Ignore updates from Matter server (prevent feedback loops)
        if annotation == "from_matter":
            return

        if not self.parent_controller:
            self.handle_error("No parent controller")
            return

        # Determine command
        command_name = "On" if value >= 0.5 else "Off"

        # Schedule command in controller's event loop
        self.parent_controller.run_coroutine(self.send_onoff_command(command_name))

    async def send_onoff_command(self, command_name: str) -> None:
        """Send OnOff command to Matter device.

        Args:
            command_name: "On" or "Off"
        """
        if not self.parent_controller or not self.parent_controller.client:
            self.handle_error("Not connected to Matter server")
            return

        if not self.eeprom_ratelimiter.limit():
            self.handle_error("Action ratelimit exceeded")
            return

        try:
            # Create command
            if command_name == "On":
                command = clusters.OnOff.Commands.On()
            else:
                command = clusters.OnOff.Commands.Off()

            # Send via client
            await self.parent_controller.client.send_device_command(
                node_id=self.node_id,
                endpoint_id=self.endpoint_id,
                command=command,
            )

            self.print(f"Sent {command_name} command")

        except Exception:
            self.handle_error(
                f"Failed to send {command_name} command:\n" f"{traceback.format_exc()}"
            )

    def on_delete(self):
        sp = self.parent_controller

        if not sp:
            return

        async def coro():
            if not sp.client:
                return
            await sp.client.remove_node(self.node_id)

        sp.run_coroutine(coro())
        return super().on_delete()
