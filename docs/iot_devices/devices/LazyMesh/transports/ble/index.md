# iot_devices.devices.LazyMesh.transports.ble

## Attributes

| [`LAZYMESH_UUID`](#iot_devices.devices.LazyMesh.transports.ble.LAZYMESH_UUID)   |    |
|---------------------------------------------------------------------------------|----|

## Classes

| [`BLETransport`](#iot_devices.devices.LazyMesh.transports.ble.BLETransport)   |    |
|-------------------------------------------------------------------------------|----|

## Module Contents

### iot_devices.devices.LazyMesh.transports.ble.LAZYMESH_UUID *= 'd1a77e11-420f-9f11-1a00-10a6beef0001'*

### *class* iot_devices.devices.LazyMesh.transports.ble.BLETransport

Bases: [`iot_devices.devices.LazyMesh.transports.ITransport`](../index.md#iot_devices.devices.LazyMesh.transports.ITransport)

#### queue *: asyncio.Queue[bytes]*

#### should_run *= True*

#### use_reliable_retransmission *= False*

#### *async* listen() → AsyncGenerator[[iot_devices.devices.LazyMesh.transports.RawPacketMetadata](../index.md#iot_devices.devices.LazyMesh.transports.RawPacketMetadata) | None, None]

#### *async* send(data: bytes)

Send raw packet bytes

#### *async* global_route(data: bytes) → bool

#### *async* close()

#### *async* maintain()
