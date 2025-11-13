from __future__ import annotations
from typing import Any
import traceback
import asyncio
import time
from iot_devices.device import Device
from .mesh import MeshNode, ITransport, Payload


class RemoteLazyMeshNode(Device):
    config_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "custom_properties": {
                "type": "array",
                "description": "Config for reading and writing non-standard datapoints",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "number"},
                        "name": {"type": "string"},
                        "datapoint": {"type": "string"},
                        "type": {"type": "string"},
                        "writable": {"type": "boolean"},
                        "resolution": {"type": "number"},
                        "min": {"type": "number"},
                        "max": {"type": "number"},
                        "unit": {"type": "string"},
                        "subtype": {"type": "string"},
                        "reliable": {
                            "type": "boolean",
                            "default": True,
                            "description": "Auto retry all attempts to set remote values",
                        },
                    },
                },
            },
        },
    }

    def __init__(self, data: dict[str, Any], **kw: Any):
        Device.__init__(self, data, **kw)
        self.device_id = 0

        self.ids_to_numeric_points: dict[int, str] = {}
        self.ids_to_string_points: dict[int, str] = {}
        self.ids_to_numeric_points_resolution: dict[int, float] = {}

        self.parent: LazyMeshNode | None = None

        # maps datapoint id to the thing we are trying to set
        # prefixed by a timestamp so we know when to just give up
        self.set_value_jobs: dict[int, tuple[float, Any]] = {}

        self.should_run = True

        self.numeric_data_point(
            "path_loss",
            min=-130,
            max=90,
            default=-130,
            unit="dB",
            description="Rough estimate of total path loss along the mesh",
        )

        self.set_rssi_ts = time.time()

        for i in self.config["custom_properties"]:
            if i["type"] == "number":
                self.ids_to_numeric_points[i["id"]] = i["datapoint"]
                self.ids_to_numeric_points_resolution[i["id"]] = i["resolution"]
                self.numeric_data_point(
                    i["datapoint"],
                    handler=self.data_id_handler(i),
                    min=i.get("min", None),
                    max=i.get("max", None),
                    unit=i.get("unit", ""),
                    subtype=i.get("subtype", ""),
                    writable=i.get("writable", True),
                )
            elif i["type"] == "string":
                self.ids_to_string_points[i["id"]] = i["datapoint"]
                self.string_data_point(
                    i["datapoint"],
                    handler=self.data_id_handler(i),
                    subtype=i.get("subtype", ""),
                    writable=i.get("writable", True),
                )
            else:
                raise Exception("Unknown type {}".format(i["type"]))

    def set_parent(self, parent: LazyMeshNode):
        if self.parent:
            raise Exception("Already have a parent")
        self.parent = parent

        def f():
            parent.node.loop.create_task(self.flush_set_value_jobs())

        parent.node.loop.call_soon_threadsafe(f)

    def on_lm_message(self, data: Payload):
        # Incomimg data is telling us the state of the remote node
        # So update accordingly

        if time.time() > (self.set_rssi_ts + 3600):
            self.set_rssi_ts = time.time()
            self.set_data_point("path_loss", (-50) - (10 * data.path_loss))

        for i in data:
            # If it's the value we are trying to set
            # then clear the job
            if i.id in self.set_value_jobs:
                if i.data == self.set_value_jobs[i.id][1]:
                    self.set_value_jobs.pop(i.id, None)

            if i.id in self.ids_to_numeric_points:
                assert isinstance(i.data, int)
                val = i.data / self.ids_to_numeric_points_resolution[i.id]
                self.set_data_point(
                    self.ids_to_numeric_points[i.id], val, None, "from_remote"
                )
            elif i.id in self.ids_to_string_points:
                assert isinstance(i.data, str)
                self.set_data_point(
                    self.ids_to_string_points[i.id], i.data, None, "from_remote"
                )

    def on_before_close(self):
        self.should_run = False
        return super().close()

    async def flush_set_value_jobs(self):
        while self.should_run:
            await asyncio.sleep(1)
            try:
                for i in list(self.set_value_jobs.keys()):
                    if self.set_value_jobs[i][0] < (time.time() - 5):
                        self.handle_error(
                            f"Timed out trying to set value for datapoint {i}"
                        )
                        self.set_value_jobs.pop(i)
                    else:
                        self.send_data_val_set_packet(
                            i, self.set_value_jobs[i][1], request_ack=True
                        )

            except Exception:
                self.handle_error("Error flushing set value jobs")
                traceback.print_exc()

    def data_id_handler(self, schema: dict[str, Any]):
        def f(v: str | int | float, _t: float, a: Any):
            if a == "from_remote":
                return
            else:
                self.send_data_val_set_packet(
                    schema["id"], v, schema.get("reliable", False)
                )

                if schema["id"] in self.set_value_jobs:
                    self.set_value_jobs.pop(schema["id"], None)
                if schema.get("reliable", False):
                    self.set_value_jobs[schema["id"]] = (time.time(), v)

        return f

    def send_data_val_set_packet(self, data_id: int, v: Any, request_ack: bool = False):
        if not self.device_id:
            return
        p = Payload()
        p.add_data(5, self.device_id)
        # Set write enable
        p.add_data(6, 1)
        p.add_data(data_id, v)

        # Request that they send back the value
        if request_ack:
            p.add_data(1, [data_id])

        def g():
            if not self.parent:
                return
            if not self.parent.channel:
                return
            self.parent.node.loop.create_task(self.parent.channel.send_packet(p))

        if not self.parent:
            return
        self.parent.node.loop.call_soon_threadsafe(g)


class LazyMeshNode(Device):
    config_schema: dict[str, Any] = {
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
            "discover_remote_nodes": {
                "type": "boolean",
                "default": True,
                "description": "Discover remote nodes",
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

            self.subdevices_by_id: dict[int, RemoteLazyMeshNode] = {}

            self.friendly_names_by_id: dict[int, str] = {}

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
                else:
                    raise ValueError(f"Unknown type {i['type']}")

            self.node = MeshNode(self.transports)

            self.channel = self.node.add_channel(self.config["channel_password"])
            # TODO type ignore bad
            self.channel.async_callback = self.on_lm_message  # type: ignore

            self.numeric_data_point(
                "local.scan_devices",
                subtype="trigger",
                handler=self.scan_req_tag_handler,
                description="Discover outher nodes on the channel",
            )
        except Exception:
            print(traceback.format_exc())
            self.handle_error("Failed to create node")

    def scan_req_tag_handler(self, *_a: Any):
        def f():
            cr = self.request_data_point_from_remote(0, 3)
            self.node.loop.create_task(cr)

        self.node.loop.call_soon_threadsafe(f)

    async def request_data_point_from_remote(self, device: int, data_point: int) -> Any:
        p = Payload()
        p.add_data(5, device)
        p.add_data(1, [data_point])
        await self.channel.send_packet(p)

    async def on_lm_message(self, data: Payload):
        try:
            is_for_us: bool = False
            addressed: int | None = None
            source: int | None = None
            write_enabled: bool = False

            for i in data:
                if i.id == 5:
                    addressed = True
                    if i.data == self.config["local_device_id"]:
                        is_for_us = True
                        break

            for i in data:
                if i.id == 2:
                    source = int(i.data)  # type: ignore

            if source is not None and not is_for_us:
                for i in data:
                    if i.id == 3:
                        self.friendly_names_by_id[source] = str(i.data)

                if source not in self.subdevices_by_id:
                    if source not in self.friendly_names_by_id:
                        await self.request_data_point_from_remote(source, 3)
                    else:
                        self.subdevices_by_id[source] = self.create_subdevice(
                            RemoteLazyMeshNode, self.friendly_names_by_id[source], {}
                        )
                        self.subdevices_by_id[source].device_id = source
                        self.subdevices_by_id[source].set_parent(self)

                if source in self.subdevices_by_id:
                    self.subdevices_by_id[source].on_lm_message(data)

            if is_for_us or not addressed:
                for i in data:
                    # data request handler
                    if i.id == 1:
                        p = Payload()
                        p.add_data(2, self.config["local_device_id"])
                        assert isinstance(i.data, list)
                        for j in i.data:
                            assert isinstance(j, int)
                            if j in self.ids_to_numeric_points:
                                point_name = self.ids_to_numeric_points[j]
                                resolution = self.ids_to_numeric_points_resolution[j]
                                d = self.datapoints[point_name].get()[0]
                                if isinstance(d, (int, float)):
                                    p.add_data(j, d * resolution)
                            elif j in self.ids_to_string_points:
                                point_name = self.ids_to_string_points[j]
                                d = self.datapoints[point_name].get()[0]
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

    def on_before_close(self):
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
