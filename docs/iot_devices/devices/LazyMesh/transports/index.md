# iot_devices.devices.LazyMesh.transports

## Submodules

* [iot_devices.devices.LazyMesh.transports.ble](ble/index.md)
* [iot_devices.devices.LazyMesh.transports.loopback](loopback/index.md)
* [iot_devices.devices.LazyMesh.transports.mqtt](mqtt/index.md)
* [iot_devices.devices.LazyMesh.transports.udp](udp/index.md)

## Classes

| [`RawPacketMetadata`](#iot_devices.devices.LazyMesh.transports.RawPacketMetadata)   |                                  |
|-------------------------------------------------------------------------------------|----------------------------------|
| [`ITransport`](#iot_devices.devices.LazyMesh.transports.ITransport)                 | Base class for protocol classes. |

## Package Contents

### *class* iot_devices.devices.LazyMesh.transports.RawPacketMetadata(raw: bytes, source: [ITransport](#iot_devices.devices.LazyMesh.transports.ITransport) | None)

#### raw

#### source *: [ITransport](#iot_devices.devices.LazyMesh.transports.ITransport) | None*

### *class* iot_devices.devices.LazyMesh.transports.ITransport

Bases: `Protocol`

Base class for protocol classes.

Protocol classes are defined as:

```default
class Proto(Protocol):
    def meth(self) -> int:
        ...
```

Such classes are primarily used with static type checkers that recognize
structural subtyping (static duck-typing).

For example:

```default
class C:
    def meth(self) -> int:
        return 0

def func(x: Proto) -> int:
    return x.meth()

func(C())  # Passes static type check
```

See PEP 544 for details. Protocol classes decorated with
@typing.runtime_checkable act as simple-minded runtime protocols that check
only the presence of given attributes, ignoring their type signatures.
Protocol classes can be generic, they are defined as:

```default
class GenProto[T](Protocol):
    def meth(self) -> T:
        ...
```

#### use_reliable_retransmission *: bool*

#### *async* listen() → AsyncGenerator[[RawPacketMetadata](#iot_devices.devices.LazyMesh.transports.RawPacketMetadata) | None, None]

Async generator that yields incoming raw packet bytes

#### *async* send(data: bytes) → None

Send raw packet bytes

#### *async* global_route(data: bytes) → bool

#### *async* close()

#### *async* maintain()
