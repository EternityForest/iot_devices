from __future__ import annotations
from typing import Protocol, AsyncGenerator


class RawPacketMetadata:
    def __init__(self, raw: bytes, source: ITransport | None):
        self.raw = raw
        self.source: ITransport | None = source


class ITransport(Protocol):
    use_reliable_retransmission: bool
    # For things like LoRa where we can repeat back out the same interface
    use_loopback: bool

    async def listen(self) -> AsyncGenerator[RawPacketMetadata | None, None]:
        """Async generator that yields incoming raw packet bytes"""
        ...
        # Keep the type checker happy
        yield None

    async def send(self, data: bytes) -> None:
        """Send raw packet bytes"""
        ...

    async def global_route(self, data: bytes) -> bool: ...

    async def close(self): ...

    async def maintain(self): ...
