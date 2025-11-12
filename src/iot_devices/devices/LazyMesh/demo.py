import time
import logging

# log to console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
# from .transports.mqtt import MQTTTransport

# from .transports.ble import BLETransport
# from .transports.udp import UDPTransport

# from .mesh import MeshNode, ITransport
# from .mesh_packet import Payload
# import time
# import asyncio

# x: list[ITransport]=[
#     ##MQTTTransport("mqtt://test.mosquitto.org:1883"),
#     BLETransport(),
#     UDPTransport()
# ]
# m =MeshNode(x)
# #m =MeshNode(MQTTTransport("mqtt://localhost:1883"))

# #m =MeshNode(LoopbackTransport())
# ch = m.add_channel("ThisMustBeGloballyUnique!!!!")

# def cb(p: Payload):
#     print("got packet")
#     for i in p:
#         print(i)

# ch.callback = cb

# while True:
#     p = Payload()
#     p.add_data(1, 1)
#     p.add_data(2, 2)
#     asyncio.run_coroutine_threadsafe(ch.send_packet(p), m.loop)
#     time.sleep(1000)

from typing import Any
from . import LazyMeshNode

config: dict[str, Any] = {
    "name": "test",
    "local_device_id": 78554,
    "channel_password": "ThisMustBeGloballyUnique!!!!",
    "enable_mqtt": True,
    "mqtt_urls": ["mqtt://test.mosquitto.org:1883"],
    "enable_udp": True,
    "local_device_name": "PythonNode",
    "discover_remote_nodes": True,
    "enable_ble": True,
    "local_data_ids": [
        {
            "id": 89,
            "name": "test",
            "type": "number",
        }
    ],
    # This config says we should be looking for a device
    # on the channel that calls itself "FriendlyNameHere"
    # And has a custom datapoint with ID 169
    # That has the following properties
    "subdevice_config": {
        "FriendlyNameHere": {
            "custom_properties": [
                {
                    "id": 196,
                    "name": "TestCustomDataPoint",
                    "datapoint": "test",
                    "type": "number",
                    "writable": True,
                    "resolution": 1,
                    "min": 0,
                    "max": 100,
                    "reliable": True,
                }
            ]
        }
    },
}


node = LazyMeshNode("test", config)
x = 1
while True:
    time.sleep(5)
    if "FriendlyNameHere" in node.subdevices:
        remote_node = node.subdevices["FriendlyNameHere"]

        remote_node.set_data_point("test", x)
        x += 1
        # remote_node.request_data_point("test")
        time.sleep(1)
        print("Remote: " + str(remote_node.datapoints["test"]))
    else:
        print("FriendlyNameHere not found")

    print("Local: " + str(node.datapoints["test"]))
