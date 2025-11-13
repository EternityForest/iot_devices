# iot_devices.devices.LazyMesh.transports.mqtt

## Attributes

| [`logger`](#iot_devices.devices.LazyMesh.transports.mqtt.logger)   |    |
|--------------------------------------------------------------------|----|

## Classes

| [`MQTTTransport`](#iot_devices.devices.LazyMesh.transports.mqtt.MQTTTransport)   |    |
|----------------------------------------------------------------------------------|----|

## Module Contents

### iot_devices.devices.LazyMesh.transports.mqtt.logger

### *class* iot_devices.devices.LazyMesh.transports.mqtt.MQTTTransport(url: str, topic_prefix: str = 'lazymesh_route_')

Bases: [`iot_devices.devices.LazyMesh.transports.ITransport`](../index.md#iot_devices.devices.LazyMesh.transports.ITransport)

#### url

#### topic_prefix *= 'lazymesh_route_'*

#### client

#### lock

#### queue *: asyncio.Queue[bytes]*

#### should_run *= True*

#### should_subscribe *: list[tuple[float, str]]* *= []*

#### ratelimiter

#### topic_crypto_keys *: dict[str, bytes]*

#### use_reliable_retransmission *= False*

#### on_disconnect(\*a, \*\*k)

#### on_reconnect(client: paho.mqtt.client.Client, userdata: Any, flags: Any, rc: Any, properties: Any = None)

#### on_message(client: paho.mqtt.client.Client, userdata: Any, msg: paho.mqtt.client.MQTTMessage)

#### *async* close()

#### *async* listen()

#### *async* maintain()

#### *async* send(data: bytes)

#### *async* global_route(data: bytes) → bool

#### *async* routing_id_to_hex_topic(routing_id: bytes) → str

#### encrypt_msg(key: bytes, payload: bytes) → bytes

#### decrypt_msg(key: bytes, data: bytes) → bytes
