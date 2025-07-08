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
    header1 |= (1 << 5) if can_use_slow_transport else 0
    header1 |= (1 << 6) if can_global_route else 0
    header1 |= (1 << 7) if was_global_routed else 0
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
                (self.path_loss << 3) | (self.last_hop_loss & 0b111),
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
