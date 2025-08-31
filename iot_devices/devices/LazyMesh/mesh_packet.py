import msgpack
from typing import Union, NamedTuple
from dataclasses import dataclass
import struct
from .transports import RawPacketMetadata
from .crypto import aes_gcm_encrypt, aes_gcm_decrypt

DataItemValue = Union[str, int, float, list[int], list[str], list[float] | bytes]


class DataItem(NamedTuple):
    id: int
    data: DataItemValue


class Payload:
    def __init__(self):
        self.items: list[DataItem] = []
        self.unix_time: int = 0
        self.metadata: RawPacketMetadata | None = None

        self.path_loss = 0

    def add_data(self, id: int, item: DataItemValue):
        self.items.append(DataItem(id, item))

    def get_data_by_id(self, id: int) -> list[DataItemValue]:
        return [v for k, v in self.items if k == id]

    def __iter__(self):
        return iter(self.items)

    @classmethod
    def from_buffer(cls, buf: bytes, raw: RawPacketMetadata) -> "Payload":
        unpacked: list[int | DataItemValue] = msgpack.unpackb(buf, raw=False)

        if not isinstance(unpacked, list):  # type: ignore
            raise ValueError("Invalid payload format")
        payload = cls()
        payload.metadata = raw
        for i in range(0, len(unpacked), 2):
            if not isinstance(unpacked[i], int):
                raise ValueError("Invalid payload format")
            dataid: int = unpacked[i]  # type: ignore
            payload.add_data(dataid, unpacked[i + 1])
        return payload

    def to_buffer(self) -> bytes:
        flat: list[int | DataItemValue] = []
        for id, val in self.items:
            flat.append(id)
            flat.append(val)
        return msgpack.packb(flat, use_bin_type=True)


# define PACKET_OVERHEAD (1 + 1 + 1 + 1 + 8 + 4 + ROUTING_ID_LEN + AUTH_TAG_LEN)

PACKET_OVERHEAD = 1 + 1 + 1 + 1 + 8 + 4 + 16 + 6

PACKET_TYPE_CONTROL = 0
PACKET_TYPE_DATA = 1
PACKET_TYPE_RELIABLE_DATA = 2

PACKET_TYPE_MASK = 0b11
TTL_OFFSET = 2
SLOW_TRANSPORT_OFFSET = 5
GLOBAL_ROUTE_OFFSET = 6
WAS_GLOBAL_ROUTED_OFFSET = 7

HEADER_2_FIRST_SEND_ATTEMPT_BIT = 0
HEADER_2_REPEATER_BIT = 1
HEADER_2_INTERESTED_BIT = 2

CONTROL_TYPE_ACK = 1
CONTROL_TYPE_REPEATER_ACK = 2


HEADER_1_BYTE_OFFSET = 0
HEADER_2_BYTE_OFFSET = 1
MESH_ROUTE_NUMBER_BYTE_OFFSET = 2
PATH_LOSS_BYTE_OFFSET = 3
ROUTING_ID_BYTE_OFFSET = 4
RANDOMNESS_BYTE_OFFSET = 20
TIME_BYTE_OFFSET = 28
CIPHERTEXT_BYTE_OFFSET = 32
AUTH_TAG_LEN = 6
PACKET_ID_64_OFFSET = RANDOMNESS_BYTE_OFFSET + 4


def add_packet_loss(packet: bytes, extra_loss: int):
    """Set the last hop field and adds to the total field"""
    if extra_loss > 7:
        extra_loss = 7

    old: int = packet[PATH_LOSS_BYTE_OFFSET]
    without_last_hop: int = old & 0b11111

    without_last_hop += extra_loss
    if without_last_hop > 31:
        without_last_hop = 31

    n = without_last_hop | (extra_loss << 5)

    modified = (
        packet[:PATH_LOSS_BYTE_OFFSET]
        + bytes([n])
        + packet[PATH_LOSS_BYTE_OFFSET + 1 :]
    )
    assert len(modified) == len(packet)
    return modified


def header1(
    packet_type: int,
    ttl: int,
    can_use_slow_transport: bool,
    can_global_route: bool,
    was_global_routed: bool,
) -> int:
    if packet_type > 3 or packet_type < 0:
        raise ValueError("Invalid packet type")
    header1 = packet_type
    header1 |= ttl << 2
    header1 |= (1 << SLOW_TRANSPORT_OFFSET) if can_use_slow_transport else 0
    header1 |= (1 << GLOBAL_ROUTE_OFFSET) if can_global_route else 0
    header1 |= (1 << WAS_GLOBAL_ROUTED_OFFSET) if was_global_routed else 0
    return header1


@dataclass
class MeshPacket:
    header: int
    header2: int
    mesh_route_num: int
    path_loss: int
    last_hop_loss: int
    routing_id: bytes
    entropy: bytes
    timestamp: int
    ciphertext: bytes | None = None
    plaintext: bytes | None = None

    ROUTING_ID_LENGTH = 16
    ENTROPY_LENGTH = 8
    TIMESTAMP_LENGTH = 4
    AUTH_TAG_LENGTH = 6

    def serialize(self) -> bytes:
        if self.ciphertext is None:
            raise ValueError("Packet not encrypted")
        buf = bytearray()
        buf.extend(
            [
                self.header,
                self.header2,
                self.mesh_route_num,
                (min(self.path_loss, 31) << 3) | (min(self.last_hop_loss, 7) & 0b111),
            ]
        )
        buf.extend(self.routing_id)
        buf.extend(self.entropy)
        buf.extend(struct.pack("<I", self.timestamp))
        buf.extend(self.ciphertext)
        return bytes(buf)

    @classmethod
    def parse(cls, data: bytes) -> "MeshPacket":
        routing_id = data[4:20]
        entropy = data[20:28]
        timestamp = struct.unpack("<I", data[28:32])[0]
        ciphertext = data[32:]
        header, header2, mesh_route_num, path_loss_byte = data[:4]
        path_loss = path_loss_byte >> 3
        last_hop_loss = path_loss_byte & 0b111
        return cls(
            header,
            header2,
            mesh_route_num,
            path_loss,
            last_hop_loss,
            routing_id,
            entropy,
            timestamp,
            ciphertext,
        )

    def encrypt(self, key: bytes):
        if self.plaintext is None:
            raise ValueError("No plaintext to encrypt")
        iv = self.entropy + struct.pack("<I", self.timestamp)
        self.ciphertext = aes_gcm_encrypt(key, self.plaintext, iv, self.AUTH_TAG_LENGTH)
        self.plaintext = None

    def decrypt(self, key: bytes):
        if self.ciphertext is None:
            raise ValueError("No ciphertext/tag")
        iv = self.entropy + struct.pack("<I", self.timestamp)
        self.plaintext = aes_gcm_decrypt(key, self.ciphertext, iv, self.AUTH_TAG_LENGTH)
        self.ciphertext = None
