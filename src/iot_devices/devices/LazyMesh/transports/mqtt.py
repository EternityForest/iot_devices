import paho.mqtt.client as mqtt
from threading import RLock
import asyncio
import time
from typing import Any
from scullery.ratelimits import RateLimiter
import os
from . import ITransport, RawPacketMetadata
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from ..crypto import aes_gcm_decrypt, aes_gcm_encrypt

import logging

logger = logging.getLogger(__name__)


class MQTTTransport(ITransport):
    def __init__(self, url: str, topic_prefix: str = "lazymesh_route_"):
        self.url = url
        self.topic_prefix = topic_prefix
        self.client = mqtt.Client()
        hostname = self.url.split("://", 1)[-1].split(":")[0]
        port = int(self.url.split("://", 1)[-1].split(":")[1])

        self.lock = RLock()
        self.queue: asyncio.Queue[bytes] = asyncio.Queue()
        self.should_run = True
        self.should_subscribe: list[tuple[float, str]] = []

        self.client.on_connect = self.on_reconnect
        self.client.on_disconnect = self.on_disconnect  # type: ignore
        self.client.on_message = self.on_message
        self.client.connect(hostname, port)
        self.client.loop_start()

        # For now just hardcode to make really sure
        # we don't DDoS a free broker
        self.ratelimiter = RateLimiter(0.2, 25)

        # topic -> routingID used as key
        self.topic_crypto_keys: dict[str, bytes] = {}

        # MQTT just relies entirely on TCP for reliability.
        self.use_reliable_retransmission = False

    def on_disconnect(self, *a, **k):
        logger.info("MQTT disconnected")

    def on_reconnect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: Any,
        rc: Any,
        properties: Any = None,
    ):
        with self.lock:
            for _, topic in self.should_subscribe:
                client.subscribe(topic)
        logger.info("MQTT Connected")

    def on_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage):
        # Decrypt using topic_crypto_keys[topic]
        routing_key = self.topic_crypto_keys.get(msg.topic)
        if routing_key:
            try:
                decrypted = self.decrypt_msg(routing_key, msg.payload)
                if decrypted:
                    # strip metadata (first byte), same as TS version
                    metadata_length = decrypted[0]
                    payload = decrypted[1 + metadata_length :]

                    header_1 = payload[0]
                    # Ensure was global routed bit is set
                    payload = payload[:1] + bytes([header_1 | (1 << 7)]) + payload[2:]

                    if self.loop:
                        asyncio.run_coroutine_threadsafe(
                            self.queue.put(payload), self.loop
                        )
            except Exception as _e:
                pass  # print(f"[MQTTTransport] decryption failed: {e}")

    async def close(self):
        self.should_run = False
        if self.client:
            self.client.disconnect()
            self.client.loop_stop()

    async def listen(self):
        self.loop = asyncio.get_running_loop()
        while True:
            data = await self.queue.get()
            yield RawPacketMetadata(data, self)

    async def maintain(self):
        while self.should_run:
            await asyncio.sleep(5)
            now = time.time()
            with self.lock:
                while self.should_subscribe and self.should_subscribe[0][0] < now - (
                    65 * 60
                ):
                    topic = self.should_subscribe[0][1]
                    self.client.unsubscribe(topic)
                    self.should_subscribe.pop(0)
                    try:
                        self.topic_crypto_keys.pop(topic)
                    except KeyError:
                        pass

    async def send(self, data: bytes):
        pass

    async def global_route(self, data: bytes) -> bool:
        header_1 = data[0]

        can_global_route = (header_1 & (1 << 6)) > 0
        was_global_routed = (header_1 & (1 << 7)) > 0

        if not can_global_route or was_global_routed:
            return False

        if not self.ratelimiter.limit():
            return False

        # set the was global routed bit
        data = data[:1] + bytes([header_1 | (1 << 7)]) + data[2:]

        # Extract routingID at offset 4 (ROUTING_ID_OFFSET)
        routing_id = data[4:20]
        topic = await self.routing_id_to_hex_topic(routing_id)

        # save routingID as encryption key
        self.topic_crypto_keys[topic] = routing_id

        # subscribe if we're not already
        now = time.time()
        with self.lock:
            if topic not in [t for _, t in self.should_subscribe]:
                self.client.subscribe(topic)
                self.should_subscribe.append((now, topic))

        encrypted_data = self.encrypt_msg(routing_id, data)
        # publish
        self.client.publish(topic, encrypted_data)

        return self.client.is_connected()

    async def routing_id_to_hex_topic(self, routing_id: bytes) -> str:
        digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
        digest.update(routing_id)
        full_hash = digest.finalize()
        short_hash = full_hash[:8]  # first 8 bytes
        hexkey = short_hash.hex()
        return f"{self.topic_prefix}{hexkey}"

    def encrypt_msg(self, key: bytes, payload: bytes) -> bytes:
        iv = os.urandom(12)

        # add metadata byte (0) as in TS version
        full_payload = b"\x00" + payload
        ct = aes_gcm_encrypt(key, full_payload, iv, 4)
        r = iv + ct
        return r

    def decrypt_msg(self, key: bytes, data: bytes) -> bytes:
        if len(data) < 12:
            raise ValueError("invalid data")
        iv = data[:12]
        ct = data[12:]
        pt = aes_gcm_decrypt(key, ct, iv, 4)

        return pt
