import time
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
    "enable_ble": True,
    "local_data_ids": [
        {
            "id": 89,
            "name": "test",
            "type": "number",
        }
    ],
}


node = LazyMeshNode("test", config)

while True:
    time.sleep(1)
    print(node.datapoints["test"])
