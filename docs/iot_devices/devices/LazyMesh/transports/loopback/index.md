# iot_devices.devices.LazyMesh.transports.loopback

## Classes

| [`LoopbackTransport`](#iot_devices.devices.LazyMesh.transports.loopback.LoopbackTransport)   |    |
|----------------------------------------------------------------------------------------------|----|

## Module Contents

### *class* iot_devices.devices.LazyMesh.transports.loopback.LoopbackTransport

Bases: [`iot_devices.devices.LazyMesh.transports.ITransport`](../index.md#iot_devices.devices.LazyMesh.transports.ITransport)

#### queue *: asyncio.Queue[bytes]*

#### *async* close()

#### *async* listen()

#### *async* send(data: bytes)

#### *async* global_route(data: bytes) → bool
