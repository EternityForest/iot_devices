from __future__ import annotations

import traceback
from typing import Any, Callable
from chip.clusters import Objects as clusters

from scullery.ratelimits import RateLimiter

from iot_devices.device import Device

from .. import Matter

GAS_NAMES = {
    0x040C: "carbon_monoxide",
    0x040D: "carbon_dioxide",
    0x0413: "nitrogen_dioxide",
    0x0415: "ozone",
    0x042A: "pm_25",
    0x042B: "formaldehyde",
    0x042C: "pm1",
    0x042D: "pm10",
    0x042E: "tvoc",
    0x042F: "radon",
    1000000: "",
}

GAS_UNITS = {
    0: "ppm",
    1: "ppb",
    2: "ppt",
    3: "mg/m3",
    4: "ug/m3",
    5: "ng/m3",
    6: "p/m3",
    7: "bq/m3",
}


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

    # Cluster handlers registry: {cluster_id: setup_function}
    CLUSTER_HANDLERS = {}

    def __init__(self, config: dict[str, Any], **kw: Any):
        super().__init__(config, **kw)

        self.eeprom_ratelimiter = RateLimiter(1 / 60, burst=100)
        self.command_ratelimiters: dict[str, RateLimiter] = {}

        self.node_id = config["node_id"]

        self.metadata["Node ID"] = config["node_id"]

        self.parent_controller: Matter.MatterController | None = self.get_parent(
            Matter.MatterController
        )

        # Subscription registry: {(endpoint_id, cluster_id, attribute_id): handler_func}
        self.subscriptions: dict[tuple[int, int, int], Callable] = {}

        # Get raw node from parent controller
        node = None
        if self.parent_controller:
            node = self.parent_controller.nodes_by_id.get(self.node_id)

        # Discover all clusters across all endpoints
        endpoints = node.endpoints if node and hasattr(node, "endpoints") else {}
        self._discover_and_setup_clusters(endpoints)

    def _discover_and_setup_clusters(self, endpoints: dict) -> None:
        """Discover all clusters in all endpoints and setup handlers.

        Args:
            endpoints: Endpoints dict {endpoint_id: MatterEndpoint, ...}
        """
        try:
            for endpoint_id, endpoint_data in endpoints.items():
                clusters_dict = getattr(endpoint_data, "clusters", {})
                if not clusters_dict and isinstance(endpoint_data, dict):
                    clusters_dict = endpoint_data.get("clusters", {})

                # Setup handler for each cluster found
                for cluster_id in clusters_dict:
                    handler = self.CLUSTER_HANDLERS.get(cluster_id)
                    if handler:
                        handler(
                            self, endpoint_id, cluster_id, clusters_dict[cluster_id]
                        )
                    else:
                        pass

        except Exception:
            self.handle_error(f"Error discovering clusters: {traceback.format_exc()}")

    def set_parent_controller(self, parent: Matter.MatterController) -> None:
        """Set reference to parent MatterController.

        Args:
            parent: The parent MatterController device
        """
        self.parent_controller = parent

    def register_subscription(
        self, endpoint_id: int, cluster_id: int, attribute_id: int, handler: Callable
    ) -> None:
        """Register a subscription for a cluster attribute.

        Args:
            endpoint_id: Endpoint ID
            cluster_id: Cluster ID
            attribute_id: Attribute ID
            handler: Callable(value) that handles updates for this attribute
        """
        key = (endpoint_id, cluster_id, attribute_id)
        self.subscriptions[key] = handler

    def get_subscriptions(self) -> dict[tuple[int, int, int], Callable]:
        """Get all registered subscriptions for this device.

        Returns:
            Dict mapping (endpoint_id, cluster_id, attribute_id) to handler functions
        """
        return self.subscriptions

    def _get_ratelimiter(self, endpoint_id: int, cluster_id: int) -> RateLimiter:
        """Get or create ratelimiter for endpoint/cluster pair.

        Args:
            endpoint_id: Endpoint ID
            cluster_id: Cluster ID

        Returns:
            RateLimiter instance
        """
        key = f"{endpoint_id}_{cluster_id}"
        if key not in self.command_ratelimiters:
            self.command_ratelimiters[key] = RateLimiter(1 / 60, burst=100)
        return self.command_ratelimiters[key]

    def _make_datapoint_handler(
        self, endpoint_id: int, cluster_id: int
    ) -> Callable[[float, float, str], None]:
        """Create handler for datapoint changes.

        Args:
            endpoint_id: Endpoint ID
            cluster_id: Cluster ID

        Returns:
            Handler function
        """

        def handler(value: float, timestamp: float, annotation: str) -> None:
            # Ignore updates from Matter server (prevent feedback loops)
            if annotation == "from_matter":
                return

            if not self.parent_controller:
                self.handle_error("No parent controller")
                return

            # Route to cluster-specific handler
            handler_func = getattr(self, f"_handle_cluster_0x{cluster_id:04x}", None)
            try:
                if handler_func:

                    async def wrapper():
                        try:
                            await handler_func(endpoint_id, value, timestamp)
                        except Exception:
                            self.handle_exception()

                    self.parent_controller.run_coroutine(wrapper())
            except Exception:
                self.handle_exception()

        return handler

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

    # Command handlers for specific clusters

    async def _handle_cluster_0x0006(
        self, endpoint_id: int, value: float, timestamp: float
    ) -> None:
        """Handle OnOff cluster (0x0006) commands.

        Args:
            endpoint_id: Endpoint ID
            value: New value (0 or 1)
            timestamp: When value was set
        """

        ratelimiter = self._get_ratelimiter(endpoint_id, 0x0006)
        if not ratelimiter.limit():
            self.handle_error(
                f"OnOff command ratelimit exceeded on endpoint {endpoint_id}"
            )
            return

        command_name = "On" if value >= 0.5 else "Off"
        command = (
            clusters.OnOff.Commands.On()
            if command_name == "On"
            else clusters.OnOff.Commands.Off()
        )

        assert self.parent_controller
        assert self.parent_controller.client
        await self.parent_controller.client.send_device_command(
            node_id=self.node_id,
            endpoint_id=endpoint_id,
            command=command,
        )

    async def _handle_cluster_0x0008(
        self, endpoint_id: int, value: float, timestamp: float
    ) -> None:
        """Handle Level Control cluster (0x0008) commands."""
        ratelimiter = self._get_ratelimiter(endpoint_id, 0x0008)
        if not ratelimiter.limit():
            self.handle_error(
                f"Level command ratelimit exceeded on endpoint {endpoint_id}"
            )
            return

        tt = self.datapoints[f"transition_time_{endpoint_id}"]

        tt_val = int(max(0, min(254, tt.get()[0] * 10)))
        level = int(max(0, min(254, value)))

        command = clusters.LevelControl.Commands.MoveToLevel(
            level=level, transitionTime=tt_val
        )

        assert self.parent_controller
        assert self.parent_controller.client

        await self.parent_controller.client.send_device_command(
            node_id=self.node_id,
            endpoint_id=endpoint_id,
            command=command,
        )

    async def _handle_cluster_0x0300(
        self, endpoint_id: int, value: float, timestamp: float
    ) -> None:
        """Handle Color Control cluster commands.

        Args:
            endpoint_id: Endpoint ID
            value: ignored because we respond to both the hue and sat tags
        """
        ratelimiter = self._get_ratelimiter(endpoint_id, 0x0008)
        if not ratelimiter.limit():
            self.handle_error(
                f"Level command ratelimit exceeded on endpoint {endpoint_id}"
            )
            return

        hue = self.datapoints[f"hue_{endpoint_id}"]
        hue_val = int(max(0, min(254, hue.get()[0])))

        sat = self.datapoints[f"saturation_{endpoint_id}"]
        sat_val = int(max(0, min(254, sat.get()[0])))

        tt_val = 0
        if f"transition_time_{endpoint_id}" in self.datapoints:
            tt = self.datapoints[f"transition_time_{endpoint_id}"]
            tt_val = int(max(0, min(254, tt.get()[0] * 10)))

        command = clusters.ColorControl.Commands.MoveToHueAndSaturation(
            hue=hue_val, saturation=sat_val, transitionTime=tt_val
        )

        assert self.parent_controller
        assert self.parent_controller.client

        await self.parent_controller.client.send_device_command(
            node_id=self.node_id,
            endpoint_id=endpoint_id,
            command=command,
        )

    # Cluster handlers

    @staticmethod
    def setup_onoff_cluster(
        device: MatterDevice,
        endpoint_id: int,
        cluster_id: int,
        cluster_dict: clusters.OnOff,
    ) -> None:
        """Setup OnOff cluster handler.

        Args:
            device: MatterDevice instance
            endpoint_id: Endpoint ID with OnOff cluster
            cluster_id: Cluster ID (0x0006)
        """
        datapoint_name = f"on_{endpoint_id}"
        dp = device.numeric_data_point(
            datapoint_name,
            min=0,
            max=1,
            subtype="bool",
            handler=device._make_datapoint_handler(endpoint_id, cluster_id),
            description=f"OnOff cluster on endpoint {endpoint_id}",
        )

        dp.set(1 if cluster_dict.onOff else 0, None, "from_matter")

        # Register subscription for OnOff attribute (0x0000)
        device.register_subscription(
            endpoint_id,
            cluster_id,
            0x0000,
            lambda value: device.set_data_point(
                datapoint_name, 1 if value else 0, annotation="from_matter"
            ),
        )

    @staticmethod
    def setup_level_control_cluster(
        device: MatterDevice,
        endpoint_id: int,
        cluster_id: int,
        cluster_dict: clusters.LevelControl,
    ) -> None:
        """Setup Level Control cluster handler (brightness/dimming).

        Args:
            device: MatterDevice instance
            endpoint: Endpoint ID with Level Control cluster
            cluster_id: Cluster ID (0x0008)
        """
        datapoint_name = f"level_{endpoint_id}"

        tt_dp_name = f"transition_time_{endpoint_id}"

        device.numeric_data_point(
            tt_dp_name,
            min=0,
            max=25,
            description=f"Level transition time {endpoint_id}",
        )

        dp = device.numeric_data_point(
            datapoint_name,
            min=0,
            max=254,
            handler=device._make_datapoint_handler(endpoint_id, cluster_id),
            description=f"Level Control (brightness) on endpoint {endpoint_id}",
        )

        if not isinstance(cluster_dict.currentLevel, clusters.Nullable):
            dp.set(int(cluster_dict.currentLevel), None, "from_matter")

        # Register subscription for CurrentLevel attribute (0x0000)
        device.register_subscription(
            endpoint_id,
            cluster_id,
            0x0000,
            lambda value: device.set_data_point(
                datapoint_name, value, annotation="from_matter"
            ),
        )

    @staticmethod
    def setup_color_control_cluster(
        device: MatterDevice,
        endpoint_id: int,
        cluster_id: int,
        cluster_dict: clusters.ColorControl,
    ) -> None:
        """Setup Color Control cluster handler (brightness/dimming).

        Args:
            device: MatterDevice instance
            endpoint: Endpoint ID
            cluster_id: Cluster ID (0x0008)
        """
        datapoint_name_hue = f"hue_{endpoint_id}"
        datapoint_name_sat = f"saturation_{endpoint_id}"

        dp = device.numeric_data_point(
            datapoint_name_hue,
            min=0,
            max=254,
            handler=device._make_datapoint_handler(endpoint_id, cluster_id),
            description=f"Color Control (hue) on endpoint {endpoint_id}",
        )

        dp = device.numeric_data_point(
            datapoint_name_sat,
            min=0,
            max=254,
            handler=device._make_datapoint_handler(endpoint_id, cluster_id),
            description=f"Color Control (sat) on endpoint {endpoint_id}",
        )

        if not isinstance(cluster_dict.currentHue, clusters.Nullable):
            dp.set(int(cluster_dict.currentHue or 0), None, "from_matter")

        if not isinstance(cluster_dict.currentSaturation, clusters.Nullable):
            dp.set(int(cluster_dict.currentSaturation or 0), None, "from_matter")

        # Register subscription for CurrentLevel attribute (0x0000)
        device.register_subscription(
            endpoint_id,
            cluster_id,
            0x0000,
            lambda value: device.set_data_point(
                datapoint_name_hue, value, annotation="from_matter"
            ),
        )
        device.register_subscription(
            endpoint_id,
            cluster_id,
            0x0001,
            lambda value: device.set_data_point(
                datapoint_name_sat, value, annotation="from_matter"
            ),
        )

    @staticmethod
    def setup_temperature_cluster(
        device: MatterDevice,
        endpoint_id: int,
        cluster_id: int,
        cluster_dict: clusters.TemperatureMeasurement,
    ) -> None:
        """Setup Temperature Measurement cluster handler.

        Args:
            device: MatterDevice instance
            endpoint_id: Endpoint ID with Temperature cluster
            cluster_id: Cluster ID (0x0402)
        """
        datapoint_name = f"temperature_{endpoint_id}"

        mx = 3000
        mn = -500

        if not isinstance(cluster_dict.maxMeasuredValue, clusters.Nullable):
            mx = cluster_dict.maxMeasuredValue / 100
        if not isinstance(cluster_dict.minMeasuredValue, clusters.Nullable):
            mn = cluster_dict.minMeasuredValue / 100

        dp = device.numeric_data_point(
            datapoint_name,
            writable=False,
            handler=None,
            description=f"Temperature on endpoint {endpoint_id} (°C)",
            min=mn,
            max=mx,
            unit="degC",
        )
        mv = cluster_dict.measuredValue
        if not isinstance(mv, clusters.Nullable):
            dp.set(mv / 100.0)
        # Register subscription for MeasuredValue attribute (0x0000)
        # Temperature is in 0.01°C units, convert to °C
        device.register_subscription(
            endpoint_id,
            cluster_id,
            0x0000,
            lambda value: device.set_data_point(
                datapoint_name,
                value / 100.0 if value is not None else 0,
                annotation="from_matter",
            ),
        )

    @staticmethod
    def setup_humidity_cluster(
        device: MatterDevice,
        endpoint_id: int,
        cluster_id: int,
        cluster_dict: clusters.RelativeHumidityMeasurement,
    ) -> None:
        """Setup Relative Humidity cluster handler.

        Args:
            device: MatterDevice instance
            endpoint_id: Endpoint ID with Humidity cluster
            cluster_id: Cluster ID (0x0405)
        """
        datapoint_name = f"humidity_{endpoint_id}"
        dp = device.numeric_data_point(
            datapoint_name,
            min=0,
            max=100,
            writable=False,
            handler=None,
            description=f"Relative Humidity on endpoint {endpoint_id} (%)",
            unit="%",
        )
        mv = cluster_dict.measuredValue
        if not isinstance(mv, clusters.Nullable):
            dp.set(mv / 100.0)

        # Register subscription for MeasuredValue attribute (0x0000)
        # Humidity is in 0.01% units, convert to %
        device.register_subscription(
            endpoint_id,
            cluster_id,
            0x0000,
            lambda value: device.set_data_point(
                datapoint_name,
                value / 100.0 if value is not None else 0,
                annotation="from_matter",
            ),
        )

    @staticmethod
    def setup_occupancy_cluster(
        device: MatterDevice,
        endpoint_id: int,
        cluster_id: int,
        cluster_dict: clusters.OccupancySensing,
    ) -> None:
        """Setup Occupancy Sensing cluster handler.

        Args:
            device: MatterDevice instance
            endpoint_id: Endpoint ID
            cluster_id: Cluster ID (0x0406)
        """
        datapoint_name = f"occupancy_{endpoint_id}"
        dp = device.numeric_data_point(
            datapoint_name,
            min=0,
            max=1,
            subtype="bool",
            writable=False,
            handler=None,
            description=f"Occupancy on endpoint {endpoint_id}",
        )
        occupancy = cluster_dict.occupancy
        if not isinstance(occupancy, clusters.Nullable):
            # Occupancy is a bitmap where bit 0 is the occupied state
            dp.set(1 if (occupancy & 0x01) else 0)

        # Register subscription for Occupancy attribute (0x0000)
        # Occupancy is a bitmap, bit 0 indicates occupied state
        device.register_subscription(
            endpoint_id,
            cluster_id,
            0x0000,
            lambda value: device.set_data_point(
                datapoint_name,
                1 if (value & 0x01) else 0 if value is not None else 0,
                annotation="from_matter",
            ),
        )

    @staticmethod
    def setup_smoke_cluster(
        device: MatterDevice,
        endpoint_id: int,
        cluster_id: int,
        cluster_dict: clusters.SmokeCoAlarm,
    ) -> None:
        """
        Args:
            device: MatterDevice instance
            endpoint_id: Endpoint ID
            cluster_id: Cluster ID (0x005C)
        """
        smoke_datapoint_name = f"smoke_{endpoint_id}"
        co_datapoint_name = f"carbon_monoxide_{endpoint_id}"

        code = device.numeric_data_point(
            f"alert_code_{endpoint_id}",
            min=0,
            max=2,
            writable=False,
            handler=None,
        )

        smoke_dp = device.numeric_data_point(
            smoke_datapoint_name,
            min=0,
            max=2,
            writable=False,
            handler=None,
        )

        co_dp = device.numeric_data_point(
            co_datapoint_name,
            min=0,
            max=2,
            writable=False,
            handler=None,
        )
        device.set_alarm("SMOKE_WARN", smoke_datapoint_name, "warning", "value == 1")

        device.set_alarm(
            "SMOKE_CRITICAL", smoke_datapoint_name, "critical", "value > 1"
        )

        device.set_alarm("CARBON_MONOXIDE", co_datapoint_name, "critical", "value > 0")
        device.set_alarm("BATTERY", code.datapoint_name, "warning", "value ==3")

        device.set_alarm("TESTING", code.datapoint_name, "warning", "value ==4")

        device.set_alarm("HARDWARE_FAULT", code.datapoint_name, "error", "value ==5")

        device.set_alarm("END_OF_SERVICE", code.datapoint_name, "error", "value ==6")

        smoke = cluster_dict.smokeState
        co = cluster_dict.COState
        smoke_dp.set(smoke or 0)
        co_dp.set(co or 0)

        code.set(cluster_dict.expressedState or 0)

        device.register_subscription(
            endpoint_id,
            cluster_id,
            0x0001,
            lambda value: device.set_data_point(
                smoke_dp.datapoint_name,
                value,
                annotation="from_matter",
            ),
        )

        device.register_subscription(
            endpoint_id,
            cluster_id,
            0x0002,
            lambda value: device.set_data_point(
                co_dp.datapoint_name,
                value,
                annotation="from_matter",
            ),
        )

        device.register_subscription(
            endpoint_id,
            cluster_id,
            0x0000,
            lambda value: device.set_data_point(
                code.datapoint_name,
                value,
                annotation="from_matter",
            ),
        )

    @staticmethod
    def setup_gas_cluster(
        device: MatterDevice,
        endpoint_id: int,
        cluster_id: int,
        cluster_dict: clusters.CarbonDioxideConcentrationMeasurement,
    ) -> None:
        """Setup Concentration Sensing cluster handler.

        Args:
            device: MatterDevice instance
            endpoint_id: Endpoint ID
            cluster_id: Cluster ID (can be multiple)
        """

        datapoint_name = f"conc_{GAS_NAMES[cluster_id]}_{endpoint_id}"
        datapoint_name2 = f"conc_{GAS_NAMES[cluster_id]}_alert_{endpoint_id}"

        mx = 1000000
        if not isinstance(cluster_dict.maxMeasuredValue, clusters.Nullable):
            mx = float(cluster_dict.maxMeasuredValue or mx)

        dp = device.numeric_data_point(
            datapoint_name,
            min=0,
            max=mx,
            writable=False,
            handler=None,
            unit=GAS_UNITS[cluster_dict.measurementUnit or 1000000],
            description=f"Gas concentration on endpoint {endpoint_id}",
        )

        dp2 = device.numeric_data_point(
            datapoint_name2,
            min=0,
            max=5,
            writable=False,
            handler=None,
            description=f"Gas alert on endpoint {endpoint_id}",
        )

        device.set_alarm(
            f"GAS_HIGH_{GAS_NAMES[cluster_id]}",
            datapoint_name2,
            "value >= 3",
            priority="error",
        )
        device.set_alarm(
            "GAS_CRITICAL_{GAS_NAMES[cluster_id]}",
            datapoint_name2,
            "value >= 4",
            priority="critical",
        )

        val = cluster_dict.measuredValue
        if not isinstance(val, clusters.Nullable):
            dp.set(val or 0)

        val = cluster_dict.levelValue
        if not isinstance(val, clusters.Nullable):
            dp2.set(val or 0)

        # Register subscription for Occupancy attribute (0x0000)
        # Occupancy is a bitmap, bit 0 indicates occupied state

        device.register_subscription(
            endpoint_id,
            cluster_id,
            0x0000,
            lambda value: device.set_data_point(
                datapoint_name,
                value,
                annotation="from_matter",
            ),
        )

        device.register_subscription(
            endpoint_id,
            cluster_id,
            0x000A,
            lambda value: device.set_data_point(
                datapoint_name2,
                value,
                annotation="from_matter",
            ),
        )

    @staticmethod
    def setup_boolean_cluster(
        device: MatterDevice,
        endpoint_id: int,
        cluster_id: int,
        cluster_dict: clusters.BooleanState,
    ) -> None:
        """Setup Boolean Sensing cluster handler.

        Args:
            device: MatterDevice instance
            endpoint_id: Endpoint ID
            cluster_id: Cluster ID (0x0045)
        """
        datapoint_name = f"boolean_{endpoint_id}"
        dp = device.numeric_data_point(
            datapoint_name,
            min=0,
            max=1,
            subtype="bool",
            writable=False,
            handler=None,
            description=f"Boolean on endpoint {endpoint_id}",
        )
        boolean = cluster_dict.stateValue
        if not isinstance(boolean, clusters.Nullable):
            # Occupancy is a bitmap where bit 0 is the occupied state
            dp.set(1 if (boolean) else 0)

        device.register_subscription(
            endpoint_id,
            cluster_id,
            0x0000,
            lambda value: device.set_data_point(
                datapoint_name,
                1 if (value) else 0 if value is not None else 0,
                annotation="from_matter",
            ),
        )

    @staticmethod
    def setup_switch_cluster(
        device: MatterDevice,
        endpoint_id: int,
        cluster_id: int,
        cluster_dict: clusters.Switch,
    ) -> None:
        """Setup Switch cluster handler.

        Args:
            device: MatterDevice instance
            endpoint_id: Endpoint ID with Switch cluster
            cluster_id: Cluster ID (0x003B)
        """
        datapoint_name = f"switch_{endpoint_id}"

        # Get NumberOfPositions to determine max value and subtype
        num_positions = 2
        if not isinstance(cluster_dict.numberOfPositions, clusters.Nullable):
            num_positions = cluster_dict.numberOfPositions

        # Use bool subtype only if exactly 2 positions
        subtype = "bool" if num_positions == 2 else ""

        dp = device.numeric_data_point(
            datapoint_name,
            min=0,
            max=num_positions - 1,
            subtype=subtype,
            writable=False,
            handler=None,
            description=f"Switch on endpoint {endpoint_id} ({num_positions} positions)",
        )

        current_pos = cluster_dict.currentPosition
        if not isinstance(current_pos, clusters.Nullable):
            dp.set(current_pos)

        # Register subscription for CurrentPosition attribute (0x0001)
        device.register_subscription(
            endpoint_id,
            cluster_id,
            0x0001,
            lambda value: device.set_data_point(
                datapoint_name,
                value if value is not None else 0,
                annotation="from_matter",
            ),
        )


# Register cluster handlers
MatterDevice.CLUSTER_HANDLERS = {
    0x0006: MatterDevice.setup_onoff_cluster,
    0x0008: MatterDevice.setup_level_control_cluster,
    0x003B: MatterDevice.setup_switch_cluster,
    0x0402: MatterDevice.setup_temperature_cluster,
    0x0405: MatterDevice.setup_humidity_cluster,
    0x0406: MatterDevice.setup_occupancy_cluster,
    0x0045: MatterDevice.setup_boolean_cluster,
    0x005C: MatterDevice.setup_smoke_cluster,
    0x0300: MatterDevice.setup_color_control_cluster,
}

for i in GAS_NAMES:
    MatterDevice.CLUSTER_HANDLERS[i] = MatterDevice.setup_gas_cluster
