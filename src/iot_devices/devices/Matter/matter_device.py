from __future__ import annotations

import traceback
from typing import Any

from iot_devices.device import Device
from chip.clusters import Objects as clusters

import __init__ as Matter


class MatterDevice(Device):
    """Represents a single Matter node with its clusters and endpoints."""

    device_type = "MatterDevice"

    config_schema = {
        "type": "object",
        "properties": {
            "node_id": {
                "type": "integer",
                "description": "Matter node ID",
            }
        },
    }

    def __init__(self, config: dict[str, Any], **kw: Any):
        super().__init__(config, **kw)

        self.node_id = config["node_id"]
        self.parent_controller: Matter.MatterController | None = None

        # Most devices use endpoint 1
        self.endpoint_id = 1

        # OnOff cluster support
        self.numeric_data_point(
            "on",
            min=0,
            max=1,
            subtype="bool",
            handler=self.on_handler,
            description="OnOff cluster state",
        )

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

    def on_matter_attribute(self, event: dict) -> None:
        """Handle attribute update from Matter server.

        Routes cluster attribute updates to the appropriate datapoint.

        Args:
            event: Attribute update event dict
        """
        try:
            endpoint_id = event.get("endpoint_id")
            cluster_id = event.get("cluster_id")
            attribute_id = event.get("attribute_id")
            value = event.get("value")

            # OnOff cluster (0x0006), OnOff attribute (0x0000)
            if (
                cluster_id == 0x0006
                and attribute_id == 0x0000
                and endpoint_id == self.endpoint_id
            ):
                # Update datapoint with "from_matter" annotation
                # to prevent feedback loop
                self.set_data_point("on", 1 if value else 0, annotation="from_matter")

        except Exception:
            self.handle_exception()
