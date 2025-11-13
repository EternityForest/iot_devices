# iot_devices.devices.LazyMesh.mesh

## Classes

| [`MeshChannel`](#iot_devices.devices.LazyMesh.mesh.MeshChannel)                   |    |
|-----------------------------------------------------------------------------------|----|
| [`QueuedOutgoingPacket`](#iot_devices.devices.LazyMesh.mesh.QueuedOutgoingPacket) |    |
| [`SeenPacketReport`](#iot_devices.devices.LazyMesh.mesh.SeenPacketReport)         |    |
| [`MeshNode`](#iot_devices.devices.LazyMesh.mesh.MeshNode)                         |    |

## Module Contents

### *class* iot_devices.devices.LazyMesh.mesh.MeshChannel(psk: bytes)

#### psk

#### temp_keys

#### callback *: Callable[[[iot_devices.devices.LazyMesh.mesh_packet.Payload](../mesh_packet/index.md#iot_devices.devices.LazyMesh.mesh_packet.Payload)], None] | None* *= None*

#### async_callback *: Callable[[[iot_devices.devices.LazyMesh.mesh_packet.Payload](../mesh_packet/index.md#iot_devices.devices.LazyMesh.mesh_packet.Payload)], Coroutine[None, None, None]] | None* *= None*

#### mesh_node *: [MeshNode](#iot_devices.devices.LazyMesh.mesh.MeshNode) | None* *= None*

#### can_global_route *= True*

#### can_use_slow_transports *= True*

#### outgoing_ttl *= 3*

#### get_temp_keys() → dict[str, bytes]

#### *async* announce(first: bool = False)

#### *async* send_packet(payload: [iot_devices.devices.LazyMesh.mesh_packet.Payload](../mesh_packet/index.md#iot_devices.devices.LazyMesh.mesh_packet.Payload))

#### *async* handle_packet(meta: [iot_devices.devices.LazyMesh.transports.RawPacketMetadata](../transports/index.md#iot_devices.devices.LazyMesh.transports.RawPacketMetadata))

### *class* iot_devices.devices.LazyMesh.mesh.QueuedOutgoingPacket(packet: bytes, expect_repeaters: int, expect_subscribers: int, exclude: list[[iot_devices.devices.LazyMesh.transports.ITransport](../transports/index.md#iot_devices.devices.LazyMesh.transports.ITransport)] = [])

#### packet

#### expect_repeaters

#### expect_subscribers

#### send_attempts *= 0*

#### last_send_time *: float* *= 0*

#### packet_id

#### exclude *= []*

#### stopSending *= False*

### *class* iot_devices.devices.LazyMesh.mesh.SeenPacketReport(packetID: bytes)

#### timestamp *: int*

#### packet_id

#### repeaters_seen *= 0*

#### subscribers_seen *= 0*

#### real_copies_seen *= 0*

### *class* iot_devices.devices.LazyMesh.mesh.MeshNode(transports: list[[iot_devices.devices.LazyMesh.transports.ITransport](../transports/index.md#iot_devices.devices.LazyMesh.transports.ITransport)])

#### transports *: list[[iot_devices.devices.LazyMesh.transports.ITransport](../transports/index.md#iot_devices.devices.LazyMesh.transports.ITransport)]*

#### channels *: dict[bytes, [MeshChannel](#iot_devices.devices.LazyMesh.mesh.MeshChannel)]*

#### should_run *= True*

#### routes_enabled *: dict[int, bool]*

#### outgoing_route_id *= 0*

#### repeater_id *= 0*

#### expect_repeater_id *= 0*

#### do_queued_packets

#### loop

#### thread_handle

#### seenPackets *: dict[bytes, [SeenPacketReport](#iot_devices.devices.LazyMesh.mesh.SeenPacketReport)]*

#### outgoingQueue *: list[[QueuedOutgoingPacket](#iot_devices.devices.LazyMesh.mesh.QueuedOutgoingPacket)]* *= []*

#### repeater_interest_by_route_id *: dict[int, float]*

#### subscriber_interest_by_channel *: collections.OrderedDict[bytes, float]*

#### *async* send_packet(b: bytes, exclude: list[[iot_devices.devices.LazyMesh.transports.ITransport](../transports/index.md#iot_devices.devices.LazyMesh.transports.ITransport)] = [], interface: [iot_devices.devices.LazyMesh.transports.ITransport](../transports/index.md#iot_devices.devices.LazyMesh.transports.ITransport) | None = None)

#### *async* send_ack(packet: bytes, destination: [iot_devices.devices.LazyMesh.transports.ITransport](../transports/index.md#iot_devices.devices.LazyMesh.transports.ITransport) | None, ack_type: int)

#### has_seen_packet(packet: bytes, source: [iot_devices.devices.LazyMesh.transports.ITransport](../transports/index.md#iot_devices.devices.LazyMesh.transports.ITransport) | None = None)

#### ensure_seen_packet_report_exists(packetID: bytes) → [SeenPacketReport](#iot_devices.devices.LazyMesh.mesh.SeenPacketReport) | None

#### close()

#### decrement_ttl(packet: bytes) → bytes | None

#### enable_route(route_id: int)

Enable repeating packets marke with the given route id

#### disable_route(route_id: int)

#### *async* handle_packet(meta: [iot_devices.devices.LazyMesh.transports.RawPacketMetadata](../transports/index.md#iot_devices.devices.LazyMesh.transports.RawPacketMetadata))

#### enqueue_packet(packet: bytes, exclude: list[[iot_devices.devices.LazyMesh.transports.ITransport](../transports/index.md#iot_devices.devices.LazyMesh.transports.ITransport)] = [])

#### *async* send_queued_packets()

#### *async* maintainance_loop()

#### add_channel(password: str)

#### remove_channel(password: str)
