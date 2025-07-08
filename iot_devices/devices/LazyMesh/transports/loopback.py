import asyncio
from . import ITransport, RawPacketMetadata


class LoopbackTransport(ITransport):
    def __init__(self):
        self.queue: asyncio.Queue[bytes] = asyncio.Queue()

    async def close(self):
        pass

    async def listen(self):
        while True:
            data = await self.queue.get()
            yield RawPacketMetadata(data, self)

    async def send(self, data: bytes):
        print("LoopbackTransport.send")
        print(data)
        self.queue.put_nowait(data)

    async def global_route(self, data: bytes) -> bool:
        return False
