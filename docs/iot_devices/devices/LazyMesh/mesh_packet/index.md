# iot_devices.devices.LazyMesh.mesh_packet

## Attributes

| [`DataItemValue`](#iot_devices.devices.LazyMesh.mesh_packet.DataItemValue)                                     |    |
|----------------------------------------------------------------------------------------------------------------|----|
| [`PACKET_OVERHEAD`](#iot_devices.devices.LazyMesh.mesh_packet.PACKET_OVERHEAD)                                 |    |
| [`PACKET_TYPE_CONTROL`](#iot_devices.devices.LazyMesh.mesh_packet.PACKET_TYPE_CONTROL)                         |    |
| [`PACKET_TYPE_DATA`](#iot_devices.devices.LazyMesh.mesh_packet.PACKET_TYPE_DATA)                               |    |
| [`PACKET_TYPE_RELIABLE_DATA`](#iot_devices.devices.LazyMesh.mesh_packet.PACKET_TYPE_RELIABLE_DATA)             |    |
| [`PACKET_TYPE_MASK`](#iot_devices.devices.LazyMesh.mesh_packet.PACKET_TYPE_MASK)                               |    |
| [`TTL_OFFSET`](#iot_devices.devices.LazyMesh.mesh_packet.TTL_OFFSET)                                           |    |
| [`SLOW_TRANSPORT_OFFSET`](#iot_devices.devices.LazyMesh.mesh_packet.SLOW_TRANSPORT_OFFSET)                     |    |
| [`GLOBAL_ROUTE_OFFSET`](#iot_devices.devices.LazyMesh.mesh_packet.GLOBAL_ROUTE_OFFSET)                         |    |
| [`WAS_GLOBAL_ROUTED_OFFSET`](#iot_devices.devices.LazyMesh.mesh_packet.WAS_GLOBAL_ROUTED_OFFSET)               |    |
| [`HEADER_2_FIRST_SEND_ATTEMPT_BIT`](#iot_devices.devices.LazyMesh.mesh_packet.HEADER_2_FIRST_SEND_ATTEMPT_BIT) |    |
| [`HEADER_2_REPEATER_BIT`](#iot_devices.devices.LazyMesh.mesh_packet.HEADER_2_REPEATER_BIT)                     |    |
| [`HEADER_2_INTERESTED_BIT`](#iot_devices.devices.LazyMesh.mesh_packet.HEADER_2_INTERESTED_BIT)                 |    |
| [`CONTROL_TYPE_ACK`](#iot_devices.devices.LazyMesh.mesh_packet.CONTROL_TYPE_ACK)                               |    |
| [`CONTROL_TYPE_REPEATER_ACK`](#iot_devices.devices.LazyMesh.mesh_packet.CONTROL_TYPE_REPEATER_ACK)             |    |
| [`HEADER_1_BYTE_OFFSET`](#iot_devices.devices.LazyMesh.mesh_packet.HEADER_1_BYTE_OFFSET)                       |    |
| [`HEADER_2_BYTE_OFFSET`](#iot_devices.devices.LazyMesh.mesh_packet.HEADER_2_BYTE_OFFSET)                       |    |
| [`MESH_ROUTE_NUMBER_BYTE_OFFSET`](#iot_devices.devices.LazyMesh.mesh_packet.MESH_ROUTE_NUMBER_BYTE_OFFSET)     |    |
| [`PATH_LOSS_BYTE_OFFSET`](#iot_devices.devices.LazyMesh.mesh_packet.PATH_LOSS_BYTE_OFFSET)                     |    |
| [`ROUTING_ID_BYTE_OFFSET`](#iot_devices.devices.LazyMesh.mesh_packet.ROUTING_ID_BYTE_OFFSET)                   |    |
| [`RANDOMNESS_BYTE_OFFSET`](#iot_devices.devices.LazyMesh.mesh_packet.RANDOMNESS_BYTE_OFFSET)                   |    |
| [`TIME_BYTE_OFFSET`](#iot_devices.devices.LazyMesh.mesh_packet.TIME_BYTE_OFFSET)                               |    |
| [`CIPHERTEXT_BYTE_OFFSET`](#iot_devices.devices.LazyMesh.mesh_packet.CIPHERTEXT_BYTE_OFFSET)                   |    |
| [`AUTH_TAG_LEN`](#iot_devices.devices.LazyMesh.mesh_packet.AUTH_TAG_LEN)                                       |    |
| [`PACKET_ID_64_OFFSET`](#iot_devices.devices.LazyMesh.mesh_packet.PACKET_ID_64_OFFSET)                         |    |

## Classes

| [`DataItem`](#iot_devices.devices.LazyMesh.mesh_packet.DataItem)     |    |
|----------------------------------------------------------------------|----|
| [`Payload`](#iot_devices.devices.LazyMesh.mesh_packet.Payload)       |    |
| [`MeshPacket`](#iot_devices.devices.LazyMesh.mesh_packet.MeshPacket) |    |

## Functions

| [`add_packet_loss`](#iot_devices.devices.LazyMesh.mesh_packet.add_packet_loss)(packet, extra_loss)   | Set the last hop field and adds to the total field   |
|------------------------------------------------------------------------------------------------------|------------------------------------------------------|
| [`header1`](#iot_devices.devices.LazyMesh.mesh_packet.header1)(→ int)                                |                                                      |

## Module Contents

### iot_devices.devices.LazyMesh.mesh_packet.DataItemValue

### *class* iot_devices.devices.LazyMesh.mesh_packet.DataItem

Bases: `NamedTuple`

#### id *: int*

#### data *: DataItemValue*

### *class* iot_devices.devices.LazyMesh.mesh_packet.Payload

#### items *: list[[DataItem](#iot_devices.devices.LazyMesh.mesh_packet.DataItem)]* *= []*

#### unix_time *: int* *= 0*

#### metadata *: [iot_devices.devices.LazyMesh.transports.RawPacketMetadata](../transports/index.md#iot_devices.devices.LazyMesh.transports.RawPacketMetadata) | None* *= None*

#### path_loss *= 0*

#### add_data(id: int, item: DataItemValue)

#### get_data_by_id(id: int) → list[DataItemValue]

#### \_\_iter_\_()

#### *classmethod* from_buffer(buf: bytes, raw: [iot_devices.devices.LazyMesh.transports.RawPacketMetadata](../transports/index.md#iot_devices.devices.LazyMesh.transports.RawPacketMetadata)) → [Payload](#iot_devices.devices.LazyMesh.mesh_packet.Payload)

#### to_buffer() → bytes

### iot_devices.devices.LazyMesh.mesh_packet.PACKET_OVERHEAD *= 38*

### iot_devices.devices.LazyMesh.mesh_packet.PACKET_TYPE_CONTROL *= 0*

### iot_devices.devices.LazyMesh.mesh_packet.PACKET_TYPE_DATA *= 1*

### iot_devices.devices.LazyMesh.mesh_packet.PACKET_TYPE_RELIABLE_DATA *= 2*

### iot_devices.devices.LazyMesh.mesh_packet.PACKET_TYPE_MASK *= 3*

### iot_devices.devices.LazyMesh.mesh_packet.TTL_OFFSET *= 2*

### iot_devices.devices.LazyMesh.mesh_packet.SLOW_TRANSPORT_OFFSET *= 5*

### iot_devices.devices.LazyMesh.mesh_packet.GLOBAL_ROUTE_OFFSET *= 6*

### iot_devices.devices.LazyMesh.mesh_packet.WAS_GLOBAL_ROUTED_OFFSET *= 7*

### iot_devices.devices.LazyMesh.mesh_packet.HEADER_2_FIRST_SEND_ATTEMPT_BIT *= 0*

### iot_devices.devices.LazyMesh.mesh_packet.HEADER_2_REPEATER_BIT *= 1*

### iot_devices.devices.LazyMesh.mesh_packet.HEADER_2_INTERESTED_BIT *= 2*

### iot_devices.devices.LazyMesh.mesh_packet.CONTROL_TYPE_ACK *= 1*

### iot_devices.devices.LazyMesh.mesh_packet.CONTROL_TYPE_REPEATER_ACK *= 2*

### iot_devices.devices.LazyMesh.mesh_packet.HEADER_1_BYTE_OFFSET *= 0*

### iot_devices.devices.LazyMesh.mesh_packet.HEADER_2_BYTE_OFFSET *= 1*

### iot_devices.devices.LazyMesh.mesh_packet.MESH_ROUTE_NUMBER_BYTE_OFFSET *= 2*

### iot_devices.devices.LazyMesh.mesh_packet.PATH_LOSS_BYTE_OFFSET *= 3*

### iot_devices.devices.LazyMesh.mesh_packet.ROUTING_ID_BYTE_OFFSET *= 4*

### iot_devices.devices.LazyMesh.mesh_packet.RANDOMNESS_BYTE_OFFSET *= 20*

### iot_devices.devices.LazyMesh.mesh_packet.TIME_BYTE_OFFSET *= 28*

### iot_devices.devices.LazyMesh.mesh_packet.CIPHERTEXT_BYTE_OFFSET *= 32*

### iot_devices.devices.LazyMesh.mesh_packet.AUTH_TAG_LEN *= 6*

### iot_devices.devices.LazyMesh.mesh_packet.PACKET_ID_64_OFFSET *= 24*

### iot_devices.devices.LazyMesh.mesh_packet.add_packet_loss(packet: bytes, extra_loss: int)

Set the last hop field and adds to the total field

### iot_devices.devices.LazyMesh.mesh_packet.header1(packet_type: int, ttl: int, can_use_slow_transport: bool, can_global_route: bool, was_global_routed: bool) → int

### *class* iot_devices.devices.LazyMesh.mesh_packet.MeshPacket

#### header *: int*

#### header2 *: int*

#### mesh_route_num *: int*

#### path_loss *: int*

#### last_hop_loss *: int*

#### routing_id *: bytes*

#### entropy *: bytes*

#### timestamp *: int*

#### ciphertext *: bytes | None* *= None*

#### plaintext *: bytes | None* *= None*

#### ROUTING_ID_LENGTH *= 16*

#### ENTROPY_LENGTH *= 8*

#### TIMESTAMP_LENGTH *= 4*

#### AUTH_TAG_LENGTH *= 6*

#### serialize() → bytes

#### *classmethod* parse(data: bytes) → [MeshPacket](#iot_devices.devices.LazyMesh.mesh_packet.MeshPacket)

#### encrypt(key: bytes)

#### decrypt(key: bytes)
