import time
import threading
from collections import OrderedDict
from typing import Callable, Coroutine
import asyncio
import traceback
from .mesh_packet import MeshPacket, Payload, header1
from . import mesh_packet
from .crypto import derive_crypto_key, derive_routing_key
from hashlib import sha256
from .transports import ITransport, RawPacketMetadata
import logging
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
                    self.mesh_node.enqueue_packet(b)

            if "next_crypto_key" in self.temp_keys:
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
                    self.mesh_node.enqueue_packet(b)

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
            self.mesh_node.enqueue_packet(packet.serialize())

    async def send_channel_ack(self, packet: bytes):
        if self.mesh_node:
            header1 = 0
            header1 |= (
                1 << mesh_packet.SLOW_TRANSPORT_OFFSET
                if self.can_use_slow_transports
                else 0
            )
            header1 |= 1 << mesh_packet.TTL_OFFSET
            header2 = 0

            p = bytes([header1, header2, mesh_packet.CONTROL_TYPE_ACK])
            packet_id = packet[
                mesh_packet.PACKET_ID_64_OFFSET : mesh_packet.PACKET_ID_64_OFFSET + 8
            ]
            ack_packet = p + packet_id
            await self.mesh_node.send_packet(ack_packet)

    async def handle_packet(self, meta: RawPacketMetadata):
        try:
            data = meta.raw
            packet = MeshPacket.parse(data)
            decoded = False

            if packet.routing_id == self.temp_keys["routing_key"]:
                packet.decrypt(self.temp_keys["crypto_key"])
                if packet.plaintext:
                    payload = Payload.from_buffer(packet.plaintext, meta)
                    payload.unix_time = packet.timestamp
                    if self.callback:
                        self.callback(payload)
                    decoded = True

            elif "closest_routing_key" in self.temp_keys:
                if packet.routing_id == self.temp_keys["closest_routing_key"]:
                    packet.decrypt(self.temp_keys["closest_crypto_key"])
                    if packet.plaintext:
                        payload = Payload.from_buffer(packet.plaintext, meta)
                        payload.unix_time = packet.timestamp
                        if self.callback:
                            self.callback(payload)
                        decoded = True

            if decoded:
                await self.send_channel_ack(meta.raw)

        except Exception:
            print("Error handling packet")
            print(traceback.format_exc())


class QueuedOutgoingPacket:
    def __init__(
        self,
        packet: bytes,
        expect_repeaters: int,
        expect_subscribers: int,
        exclude: list[ITransport] = [],
    ):
        if len(packet) < 32:
            raise ValueError("Packet must be at least 32 bytes long")

        self.packet = packet
        self.expect_repeaters = expect_repeaters
        self.expect_subscribers = expect_subscribers

        self.repeaters_seen = 0
        self.subscribers_seen = 0

        self.send_attempts = 0
        self.last_send_time: float = 0
        self.packet_id = packet[24:32]

        self.exclude = exclude


class SeenPacketReport:
    def __init__(self, packet: bytes):
        self.timestamp: int = struct.unpack(
            "<I",
            packet[mesh_packet.TIME_BYTE_OFFSET : mesh_packet.TIME_BYTE_OFFSET + 4],
        )[0]

        self.packet_id = packet[
            mesh_packet.PACKET_ID_64_OFFSET : mesh_packet.PACKET_ID_64_OFFSET + 8
        ]


class MeshNode:
    def __init__(self, transports: list[ITransport]):
        self.transports: list[ITransport] = transports
        self.channels: dict[bytes, MeshChannel] = {}
        self.should_run = True

        self.do_queued_packets = asyncio.Event()
        self.loop = asyncio.new_event_loop()
        asyncio.run_coroutine_threadsafe(self._run(), self.loop)
        asyncio.run_coroutine_threadsafe(self.maintainance_loop(), self.loop)
        asyncio.run_coroutine_threadsafe(self.send_queued_packets(), self.loop)
        self.thread_handle = threading.Thread(
            target=self.loop.run_forever, daemon=True, name="MeshNodeThread"
        )
        self.thread_handle.start()

        self.seenPackets: dict[bytes, SeenPacketReport] = {}
        self.outgoingQueue: list[QueuedOutgoingPacket] = []

        self.repeater_interest_by_route_id: dict[int, float] = {}
        self.subscriber_interest_by_channel: OrderedDict[bytes, float] = OrderedDict()

    async def send_packet(
        self,
        b: bytes,
        exclude: list[ITransport] = [],
        interface: ITransport | None = None,
    ):
        self.has_seen_packet(b)

        c: list[Coroutine[None, None, None]] = []

        global_routed = False

        header_1 = b[0]
        header_2 = b[1]

        first_attempt = header_2 & (1 << mesh_packet.HEADER_2_FIRST_SEND_ATTEMPT_BIT)

        packet_type = header_1 & 0b11

        can_global_route = (header_1 & (1 << 6)) > 0
        was_global_routed = (header_1 & (1 << 7)) > 0

        # Controls don't get global routed
        if first_attempt and packet_type in [1, 2]:
            if can_global_route and (not was_global_routed):
                for i in self.transports:
                    if i in exclude:
                        continue
                    if interface and not i == interface:
                        continue
                    if await i.global_route(b):
                        global_routed = True

        # Mark as already global routed if at least one global transport worked
        # Otherwise everyone else will be spewing packets we already sent
        if global_routed and packet_type in [1, 2]:
            header_1 = b[0]
            header_1 = header_1 | (1 << 7)
            b = b[:0] + bytes([header_1]) + b[1:]

        for i in self.transports:
            if i in exclude:
                continue
            if interface and not i == interface:
                continue
            c.append(i.send(b))

        await asyncio.gather(*c)

    def has_seen_packet(self, packet: bytes, source: ITransport | None = None):
        # Too small to be anthig but control and control doesn't have replay detect

        if len(packet) < mesh_packet.PACKET_OVERHEAD:
            return False

        packetID: bytes = packet[
            mesh_packet.PACKET_ID_64_OFFSET : mesh_packet.PACKET_ID_64_OFFSET + 8
        ]

        report = SeenPacketReport(packet)

        packetTime = report.timestamp

        if packetTime < time.time() - 180:
            return True

        if packetTime > time.time() + 120:
            return True

        for i in self.outgoingQueue:
            if i.packet_id == packetID:
                if source and source.use_reliable_retransmission:
                    i.repeaters_seen += 1

        seen = False
        if packetID in self.seenPackets:
            if len(self.seenPackets) > 10**6:
                # Oldest packet is too recent to clear, return true, we have to assume
                # everything has been seen since we can't actually check
                for i in self.seenPackets:
                    if self.seenPackets[i].timestamp > time.time() - 180:
                        return True
                    break

                # Delete old
                for i in range(1000):
                    first = next(iter(self.seenPackets))
                    if self.seenPackets[first].timestamp < time.time() - 180:
                        del self.seenPackets[first]
                    else:
                        break

            self.seenPackets[packetID] = report
            seen = True

        return seen

    def close(self):
        self.should_run = False
        self.loop.call_soon_threadsafe(self.loop.stop)

    def decrement_ttl(self, packet: bytes) -> bytes | None:
        h = packet[0]
        ttl = h & (0b11 << 2)
        without_ttl = h & ~(0b11 << 2)
        if ttl == 0:
            return None

        h = without_ttl | (ttl - 1)

        return packet[:0] + bytes([h]) + packet[1:]

    async def _run(self):
        try:
            merged = stream.merge(*[i.listen() for i in self.transports])
            async with merged.stream() as s:
                async for i in s:
                    if i:
                        await self.handle_packet(i)
        except Exception:
            print(traceback.format_exc())

    async def handle_packet(self, meta: RawPacketMetadata):
        if self.has_seen_packet(meta.raw):
            return

        packet_type = meta.raw[0] & 0b11

        if packet_type in [1, 2]:
            decremented = self.decrement_ttl(meta.raw)
            if decremented:
                self.enqueue_packet(decremented, exclude=[meta.source])

            for channel in self.channels.values():
                await channel.handle_packet(meta)

        # control
        if packet_type == 0:
            control_type = meta.raw[1]
            control_payload = meta.raw[2:]

            if meta.source.use_reliable_retransmission:
                if control_type == mesh_packet.CONTROL_TYPE_ACK:
                    for i in self.outgoingQueue:
                        if i.packet_id == control_payload:
                            i.subscribers_seen += 1

                elif control_type == mesh_packet.CONTROL_TYPE_REPEATER_ACK:
                    for i in self.outgoingQueue:
                        if i.packet_id == control_payload:
                            i.repeaters_seen += 1

    def enqueue_packet(self, packet: bytes, exclude: list[ITransport] = []):
        if len(packet) < mesh_packet.PACKET_OVERHEAD:
            raise ValueError("Can't queue this, it doesn't look like a data packet")

        packet_type = packet[0] & 0b11

        if packet_type == 0:
            raise ValueError("Can't queue this, it looks like a control packet")

        if packet_type == mesh_packet.PACKET_TYPE_RELIABLE_DATA:
            route_number = packet[mesh_packet.MESH_ROUTE_NUMBER_BYTE_OFFSET]
            routing_id = packet[
                mesh_packet.ROUTING_ID_BYTE_OFFSET : mesh_packet.ROUTING_ID_BYTE_OFFSET
                + 8
            ]

            expect_repeaters = min(
                4, int(self.repeater_interest_by_route_id.get(route_number, 0) + 0.7)
            )

            expect_subscribers = min(
                6, int(self.subscriber_interest_by_channel.get(routing_id, 0) + 0.7)
            )
        else:
            expect_repeaters = 0
            expect_subscribers = 0

        # print(
        #     f"Queuing packet with {expect_repeaters} expected repeaters and {expect_subscribers} expected subscribers"
        # )

        self.outgoingQueue.append(
            QueuedOutgoingPacket(packet, expect_repeaters, expect_subscribers, exclude)
        )

        self.do_queued_packets.set()

    async def send_queued_packets(self):
        while self.should_run:
            try:
                self.do_queued_packets.clear()
                try:
                    await asyncio.wait_for(self.do_queued_packets.wait(), 0.2)
                except asyncio.TimeoutError:
                    pass

                for i in self.outgoingQueue:
                    # print("Sending packet attempt", i.send_attempts)
                    if i.last_send_time < time.time() - 0.2:
                        i.last_send_time = time.time()
                        i.send_attempts += 1

                        # Set or clear the first send attempt bit
                        if i.send_attempts > 1:
                            header2 = i.packet[1]
                            header2 &= ~(
                                1 << mesh_packet.HEADER_2_FIRST_SEND_ATTEMPT_BIT
                            )
                            i.packet = i.packet[:1] + bytes([header2]) + i.packet[2:]
                        else:
                            header2 = i.packet[1]
                            header2 |= 1 << mesh_packet.HEADER_2_FIRST_SEND_ATTEMPT_BIT
                            i.packet = i.packet[:1] + bytes([header2]) + i.packet[2:]

                        await self.send_packet(i.packet, exclude=i.exclude)

                torm: list[QueuedOutgoingPacket] = []
                for i in self.outgoingQueue:
                    if i.send_attempts > 5:
                        torm.append(i)
                    if i.subscribers_seen >= i.expect_subscribers:
                        if i.repeaters_seen >= i.expect_repeaters:
                            torm.append(i)

                for i in torm:
                    # print("Done with packet after", i.send_attempts, "attempts")
                    # print(i.repeaters_seen, i.expect_repeaters, i.subscribers_seen, i.expect_subscribers)
                    self.outgoingQueue.remove(i)
                    route_id = i.packet[mesh_packet.MESH_ROUTE_NUMBER_BYTE_OFFSET]

                    old = self.repeater_interest_by_route_id.get(route_id, 0)
                    new = i.repeaters_seen

                    if new > old:
                        self.repeater_interest_by_route_id[route_id] = new
                    else:
                        new = old * 0.90 + new * 0.10
                        self.repeater_interest_by_route_id[route_id] = new

                    channel_hash = i.packet[
                        mesh_packet.ROUTING_ID_BYTE_OFFSET : mesh_packet.ROUTING_ID_BYTE_OFFSET
                        + 16
                    ]

                    old = self.subscriber_interest_by_channel.get(channel_hash, 0)
                    new = i.subscribers_seen

                    if new > old:
                        self.subscriber_interest_by_channel[channel_hash] = new
                    else:
                        new = old * 0.90 + new * 0.10
                        self.subscriber_interest_by_channel[channel_hash] = new

                    if len(self.subscriber_interest_by_channel) > 3096:
                        self.subscriber_interest_by_channel = OrderedDict(
                            list(self.subscriber_interest_by_channel.items())[-2048:]
                        )
            except Exception:
                print(traceback.format_exc())
                logging.error("Error in send queued packets")

    async def maintainance_loop(self):
        try:
            for channel in self.channels.values():
                await channel.announce(first=True)

            while self.should_run:
                time_till_next_hour = 3600 - time.time() % 3600
                await asyncio.sleep(max(time_till_next_hour, 300))
                for channel in self.channels.values():
                    await channel.announce()

        except Exception:
            print(traceback.format_exc())
            logging.error("Error in maintainance loop")

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
