# iot_devices.devices.LazyMesh.transports.udp

## Attributes

| [`MCAST_GROUP`](#iot_devices.devices.LazyMesh.transports.udp.MCAST_GROUP)   |    |
|-----------------------------------------------------------------------------|----|
| [`MCAST_PORT`](#iot_devices.devices.LazyMesh.transports.udp.MCAST_PORT)     |    |

## Classes

| [`UDPTransport`](#iot_devices.devices.LazyMesh.transports.udp.UDPTransport)   |    |
|-------------------------------------------------------------------------------|----|

## Module Contents

### iot_devices.devices.LazyMesh.transports.udp.MCAST_GROUP *= '224.0.0.251'*

### iot_devices.devices.LazyMesh.transports.udp.MCAST_PORT *= 2221*

### *class* iot_devices.devices.LazyMesh.transports.udp.UDPTransport

Bases: [`iot_devices.devices.LazyMesh.transports.ITransport`](../index.md#iot_devices.devices.LazyMesh.transports.ITransport)

#### sock *= None*

#### use_reliable_retransmission *= True*

#### *async* setup()

#### *async* listen() → AsyncGenerator[[iot_devices.devices.LazyMesh.transports.RawPacketMetadata](../index.md#iot_devices.devices.LazyMesh.transports.RawPacketMetadata) | None, None]

#### *async* send(data: bytes)

#### *async* global_route(data: bytes) → bool

#### *async* close()

#### *async* maintain()
