from typing import Any
import traceback
from iot_devices.device import Device
from .mesh import MeshNode, ITransport, Payload


class LazyMeshNode(Device):
    json_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "local_device_id": {
                "type": "number",
                "default": 1,
                "description": "The ID of the local node, must be unique on the channel",
            },
            "local_device_name": {
                "type": "string",
                "default": "",
                "description": "The name of the local node shown to the net",
            },
            "channel_password": {
                "type": "string",
                "default": "",
                "description": "The password for the channel",
            },
            "enable_mqtt": {
                "type": "boolean",
                "default": True,
                "description": "Enable MQTT",
            },
            "mqtt_urls": {
                "type": "array",
                "items": {"type": "string"},
                "default": ["mqtt://localhost:1883", "mqtt://test.mosquitto.org:1883"],
            },
            "enable_udp": {
                "type": "boolean",
                "default": True,
                "description": "Enable UDP",
            },
            "enable_ble": {
                "type": "boolean",
                "default": True,
                "description": "Enable BLE",
            },
            "local_data_ids": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "number", "required": True, "default": 0},
                        "name": {"type": "string", "required": True, "default": ""},
                        "type": {
                            "type": "string",
                            "enum": ["string", "number"],
                            "required": True,
                            "default": "number",
                        },
                    },
                    "readable": {"type": "boolean", "default": True},
                    "writable": {"type": "boolean", "default": False},
                    "resolution": {
                        "type": "number",
                        "default": 16384,
                        "required": False,
                        "description": "Multiplier to convert values into integers to send",
                    },
                    "min": {
                        "type": "number",
                        "required": False,
                        "description": "Minimum value",
                    },
                    "max": {
                        "type": "number",
                        "required": False,
                        "description": "Maximum value",
                    },
                    "unit": {"type": "string", "default": "", "description": "Unit"},
                    "subtype": {
                        "type": "string",
                        "default": "",
                        "enum": ["bool", "trigger", ""],
                    },
                },
            },
        },
    }

    def data_id_handler(self, schema: dict[str, Any]):
        def f(v: str | int | float, t: float, a: Any):
            if a == "from_remote":
                return

            else:
                p = Payload()
                p.add_data(schema["id"], v)

                def g():
                    self.node.loop.create_task(self.channel.send_packet(p))

                self.node.loop.call_soon_threadsafe(g)

        return f

    def __init__(self, name: str, data: dict[str, Any], **kw: Any):
        Device.__init__(self, name, data, **kw)

        try:
            self.transports: list[ITransport] = []

            if self.config["enable_mqtt"]:
                from iot_devices.devices.LazyMesh.transports.mqtt import MQTTTransport

                for i in self.config["mqtt_urls"]:
                    self.transports.append(MQTTTransport(i))

            if self.config["enable_udp"]:
                from iot_devices.devices.LazyMesh.transports.udp import UDPTransport

                self.transports.append(UDPTransport())

            if self.config["enable_ble"]:
                from iot_devices.devices.LazyMesh.transports.ble import BLETransport

                self.transports.append(BLETransport())

            self.ids_to_numeric_points: dict[int, str] = {}
            self.ids_to_string_points: dict[int, str] = {}
            self.ids_to_numeric_points_resolution: dict[int, float] = {}

            for i in self.config["local_data_ids"]:
                if i["type"] == "number":
                    self.numeric_data_point(
                        i["name"],  # type: ignore
                        min=i.get("min", None),  # type: ignore
                        max=i.get("max", None),  # type: ignore
                        unit=i.get("unit", ""),  # type: ignore
                        subtype=i.get("subtype", ""),  # type: ignore
                        writable=i.get("writable", False),  # type: ignore
                        resolution=i.get("resolution", 1),  # type: ignore
                        from_remote=i.get("from_remote", False),  # type: ignore
                        data_id=i.get("id", 0),  # type: ignore
                        data_id_handler=self.data_id_handler(i),
                    )
                    self.ids_to_numeric_points[i["id"]] = i["name"]
                    self.ids_to_numeric_points_resolution[i["id"]] = i.get(
                        "resolution", 1
                    )

                elif i["type"] == "string":
                    self.string_data_point(
                        i["name"],  # type: ignore
                        writable=i.get("writable", False),  # type: ignore
                        from_remote=i.get("from_remote", False),  # type: ignore
                        data_id=i.get("id", 0),  # type: ignore
                        data_id_handler=self.data_id_handler(i),
                    )
                    self.ids_to_string_points[i["id"]] = i["name"]

            self.node = MeshNode(self.transports)

            self.channel = self.node.add_channel(self.config["channel_password"])
            self.channel.callback = self.on_lm_message
        except Exception:
            print(traceback.format_exc())
            self.handle_error("Failed to create node")

    def on_lm_message(self, data: Payload):
        try:
            is_for_us: bool = False
            addressed: bool = False
            write_enabled: bool = False

            for i in data:
                print(i.id, i.data)
                if i.id == 5:
                    addressed = True
                    if i.data == self.config["local_device_id"]:
                        is_for_us = True
                        break

            if is_for_us or not addressed:
                for i in data:
                    # data request handler
                    if i.id == 1:
                        print("data request")
                        p = Payload()
                        p.add_data(2, self.config["local_device_id"])
                        assert isinstance(i.data, list)
                        for j in i.data:
                            assert isinstance(j, int)
                            if j in self.ids_to_numeric_points:
                                print("numeric")
                                point_name = self.ids_to_numeric_points[j]
                                resolution = self.ids_to_numeric_points_resolution[j]
                                d = self.datapoints[point_name]
                                if isinstance(d, (int, float)):
                                    p.add_data(j, d * resolution)
                            elif j in self.ids_to_string_points:
                                point_name = self.ids_to_string_points[j]
                                d = self.datapoints[point_name]
                                if isinstance(d, str):
                                    if len(d) < 65:
                                        p.add_data(j, d)
                            elif j == 2:
                                p.add_data(j, self.config["local_device_id"])
                            elif j == 3:
                                p.add_data(j, self.config["local_device_name"])

                        def f():
                            self.node.loop.create_task(self.channel.send_packet(p))

                        self.node.loop.call_soon_threadsafe(f)

                    if i.id == 6 and i.data == 1:
                        write_enabled = True

                    if write_enabled:
                        if i.id in self.ids_to_numeric_points:
                            point_name = self.ids_to_numeric_points[i.id]
                            resolution = self.ids_to_numeric_points_resolution[i.id]
                            d = i.data
                            if isinstance(d, (int, float)):
                                self.set_data_point(
                                    point_name, d * resolution, None, "from_remote"
                                )

                        elif i.id in self.ids_to_string_points:
                            point_name = self.ids_to_string_points[i.id]
                            d = i.data
                            if isinstance(d, str):
                                self.set_data_point(point_name, d, None, "from_remote")

        except Exception:
            print(traceback.format_exc())
            self.handle_error("Failed to handle lm message")

    def close(self):
        try:
            self.node.close()
        except Exception:
            pass
        return super().close()


class LazyMeshLocalNode(LazyMeshNode):
    def __init__(self, name: str, data: dict[str, Any], **kw: Any):
        LazyMeshNode.__init__(self, name, data, **kw)
        self.node.add_channel(self.config["channel_password"])

    def on_lm_message(self, data: Payload):
        return super().on_lm_message(data)
