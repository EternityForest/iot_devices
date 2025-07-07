import asyncio
from typing import AsyncGenerator
from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from . import ITransport

LAZYMESH_UUID = "d1a77e11-420f-9f11-1a00-10a6beef0001"


class BLETransport(ITransport):
    def __init__(self):
        self.queue: asyncio.Queue[bytes] = asyncio.Queue()
        self.should_run = True

    async def listen(self) -> AsyncGenerator[bytes | None, None]:
        async def detection_callback(
            device: BLEDevice, advertisement_data: AdvertisementData
        ):
            # Check if our UUID is present
            svc_data = advertisement_data.service_data.get(LAZYMESH_UUID)
            if svc_data:
                await self.queue.put(svc_data)

        async with BleakScanner(detection_callback):
            while self.should_run:
                data = await self.queue.get()
                yield data

    async def send(self, data: bytes):
        """Send raw packet bytes"""

    async def global_route(self, data: bytes) -> bool:
        return False

    async def close(self):
        self.should_run = False

    async def maintain(self):
        pass
