import asyncio
import socket
import struct
from typing import AsyncGenerator
from . import ITransport, RawPacketMetadata

MCAST_GROUP = "224.0.0.251"
MCAST_PORT = 2221


class UDPTransport(ITransport):
    def __init__(self):
        self.sock = None
        self.use_reliable_retransmission = True

    async def setup(self):
        # Create UDP socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self.sock.bind(("", MCAST_PORT))  # bind to all interfaces
        except Exception as e:
            raise RuntimeError(f"Failed to bind UDP socket: {e}")

            # Join multicast group
            group = socket.inet_aton(MCAST_GROUP)
            mreq = struct.pack("4s4s", group, socket.inet_aton("0.0.0.0"))

            # Set the socket option to join the multicast group
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

        # Set non-blocking
        self.sock.setblocking(False)

    async def listen(self) -> AsyncGenerator[RawPacketMetadata | None, None]:
        if not self.sock:
            await self.setup()
        assert self.sock
        loop = asyncio.get_running_loop()

        while True:
            try:
                data, _addr = await loop.sock_recvfrom(self.sock, 4096)
                yield RawPacketMetadata(data, self)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[UDPTransport] recv error: {e}")
                continue

    async def send(self, data: bytes):
        if not self.sock:
            await self.setup()
        assert self.sock
        loop = asyncio.get_running_loop()
        try:
            await loop.sock_sendto(self.sock, data, (MCAST_GROUP, MCAST_PORT))
        except Exception as e:
            print(f"[UDPTransport] send error: {e}")

    async def global_route(self, data: bytes) -> bool:
        return False

    async def close(self):
        if self.sock:
            self.sock.close()
            self.sock = None

    async def maintain(self):
        pass
