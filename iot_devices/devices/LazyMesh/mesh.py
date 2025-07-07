import time
import threading
from typing import Callable, Coroutine
import asyncio
from .mesh_packet import MeshPacket, Payload, header1
from .crypto import derive_crypto_key, derive_routing_key
from hashlib import sha256
from .transports import ITransport

from aiostream import stream

import os
import struct


class MeshChannel:
    def __init__(self, psk: bytes):
        self.psk = psk
        self.temp_keys = self.get_temp_keys()
        self.callback: Callable[[Payload], None] | None = None
        self.mesh_node: MeshNode | None = None
        self.can_global_route = True
        self.can_use_slow_transports = True
        self.outgoing_ttl = 3

    def get_temp_keys(self) -> dict[str, bytes]:
        unix_time = int(time.time())
        hours_since_epoch = unix_time // 3600

        next_hour = (unix_time + 600) // 3600
        prev_hour = (unix_time - 600) // 3600

        keys: dict[str, bytes] = {
            "crypto_key": derive_crypto_key(self.psk, hours_since_epoch),
            "routing_key": derive_routing_key(self.psk, hours_since_epoch),
        }
        keys["next_routing_key"] = derive_routing_key(self.psk, next_hour)
        keys["next_crypto_key"] = derive_crypto_key(self.psk, next_hour)

        if next_hour != hours_since_epoch:
            keys["closest_routing_key"] = keys["next_routing_key"]
            keys["closest_crypto_key"] = keys["next_crypto_key"]
        elif prev_hour != hours_since_epoch:
            keys["closest_routing_key"] = derive_routing_key(self.psk, prev_hour)
            keys["closest_crypto_key"] = derive_crypto_key(self.psk, prev_hour)
        return keys

    async def announce(self, first: bool = False):
        self.temp_keys = self.get_temp_keys()
        if self.mesh_node:
            payload = Payload()
            raw = payload.to_buffer()

            h = header1(
                packet_type=1,
                ttl=self.outgoing_ttl,
                can_use_slow_transport=self.can_use_slow_transports,
                can_global_route=self.can_global_route,
                was_global_routed=False,
            )
            if first:
                packet = MeshPacket(
                    header=h,
                    header2=0,
                    mesh_route_num=0,
                    path_loss=0,
                    last_hop_loss=0,
                    routing_id=self.temp_keys["routing_key"],
                    entropy=os.urandom(8),
                    timestamp=int(time.time()),
                    plaintext=raw,
                )
                packet.encrypt(self.temp_keys["crypto_key"])

                b = packet.serialize()
                if self.mesh_node:
                    await self.mesh_node.send_packet(b)

            if "next_crypto_key" in self.temp_keys:
                h = header1(
                    packet_type=1,
                    ttl=self.outgoing_ttl,
                    can_use_slow_transport=self.can_use_slow_transports,
                    can_global_route=self.can_global_route,
                    was_global_routed=False,
                )
                packet = MeshPacket(
                    header=h,
                    header2=0,
                    mesh_route_num=0,
                    path_loss=0,
                    last_hop_loss=0,
                    routing_id=self.temp_keys["next_routing_key"],
                    entropy=os.urandom(8),
                    timestamp=int(time.time()),
                    plaintext=raw,
                )
                packet.encrypt(self.temp_keys["next_crypto_key"])

                b = packet.serialize()
                if self.mesh_node:
                    await self.mesh_node.send_packet(b)

    async def send_packet(self, payload: Payload):
        timestamp = int(time.time())
        entropy = os.urandom(8)
        raw_payload = payload.to_buffer()
        h = header1(
            packet_type=1,
            ttl=self.outgoing_ttl,
            can_use_slow_transport=self.can_use_slow_transports,
            can_global_route=self.can_global_route,
            was_global_routed=False,
        )
        packet = MeshPacket(
            header=h,
            header2=0,
            mesh_route_num=0,
            path_loss=0,
            last_hop_loss=0,
            routing_id=self.temp_keys["routing_key"],
            entropy=entropy,
            timestamp=timestamp,
            plaintext=raw_payload,
        )
        packet.encrypt(self.temp_keys["crypto_key"])
        if self.mesh_node:
            await self.mesh_node.send_packet(packet.serialize())

    async def handle_packet(self, data: bytes):
        packet = MeshPacket.parse(data)
        if packet.routing_id == self.temp_keys["routing_key"]:
            packet.decrypt(self.temp_keys["crypto_key"])
            if packet.plaintext:
                payload = Payload.from_buffer(packet.plaintext)
                payload.unix_time = packet.timestamp
                if self.callback:
                    self.callback(payload)

        elif "closest_routing_key" in self.temp_keys:
            if packet.routing_id == self.temp_keys["closest_routing_key"]:
                packet.decrypt(self.temp_keys["closest_crypto_key"])
                if packet.plaintext:
                    payload = Payload.from_buffer(packet.plaintext)
                    payload.unix_time = packet.timestamp
                    if self.callback:
                        self.callback(payload)


class MeshNode:
    def __init__(self, transports: list[ITransport]):
        self.transports: list[ITransport] = transports
        self.channels: dict[bytes, MeshChannel] = {}
        self.should_run = True

        self.loop = asyncio.new_event_loop()
        asyncio.run_coroutine_threadsafe(self._run(), self.loop)
        asyncio.run_coroutine_threadsafe(self.maintainance_loop(), self.loop)
        self.thread_handle = threading.Thread(
            target=self.loop.run_forever, daemon=True, name="MeshNodeThread"
        )
        self.thread_handle.start()

        self.seenPackets: dict[bytes, float] = {}

    async def send_packet(self, b: bytes):
        if self.has_seen_packet(b):
            return
        c: list[Coroutine[None, None, None]] = []

        global_routed = False
        for i in self.transports:
            if await i.global_route(b):
                global_routed = True

        # Mark as already global routed if at least one global transport worked
        # Otherwise everyone else will be spewing packets we already sent
        if global_routed:
            header_1 = b[0]
            header_1 = header_1 | (1 << 7)
            b = b[:0] + bytes([header_1]) + b[1:]

        for i in self.transports:
            c.append(i.send(b))

        await asyncio.gather(*c)

    def has_seen_packet(self, packet: bytes):
        packetID: bytes = packet[20:28]

        packetTime: float = struct.unpack("<I", packet[28:32])[0]
        if packetTime < time.time() - 180:
            return True

        if packetTime > time.time() + 120:
            return True

        if packetID in self.seenPackets:
            return True
        else:
            if len(self.seenPackets) > 10**6:
                # Oldest packet is too recent to clear, return true, we have to assume
                # everything has been seen since we can't actually check
                for i in self.seenPackets:
                    if self.seenPackets[i] > time.time() - 180:
                        return True
                    break

                # Delete old
                for i in range(1000):
                    first = next(iter(self.seenPackets))
                    if self.seenPackets[first] < time.time() - 180:
                        del self.seenPackets[first]
                    else:
                        break

            self.seenPackets[packetID] = time.time()
            return False

    def close(self):
        self.should_run = False
        self.loop.call_soon_threadsafe(self.loop.stop)

    async def _run(self):
        merged = stream.merge(*[i.listen() for i in self.transports])
        async with merged.stream() as s:
            async for i in s:
                if i:
                    if self.has_seen_packet(i):
                        continue
                    for channel in self.channels.values():
                        await channel.handle_packet(i)

    async def maintainance_loop(self):
        for channel in self.channels.values():
            await channel.announce(first=True)

        while self.should_run:
            time_till_next_hour = 3600 - time.time() % 3600
            await asyncio.sleep(max(time_till_next_hour, 300))
            for channel in self.channels.values():
                await channel.announce()

    def add_channel(self, password: str):
        psk = password.encode("utf-8")
        psk = sha256(psk).digest()[:16]

        self.channels[psk] = MeshChannel(psk)
        self.channels[psk].mesh_node = self

        def f():
            self.loop.create_task(self.channels[psk].announce(first=True))

        self.loop.call_soon_threadsafe(f)
        return self.channels[psk]

    def remove_channel(self, password: str):
        psk = password.encode("utf-8")
        psk = sha256(psk).digest()[:16]
        del self.channels[psk]
