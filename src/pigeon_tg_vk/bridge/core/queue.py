import asyncio
import logging
from collections.abc import Awaitable, Callable

from pigeon_tg_vk.bridge.core.models import IncomingMessage

logger = logging.getLogger(__name__)

MessageHandler = Callable[[IncomingMessage], Awaitable[None]]
Slot = asyncio.Future

SLOT_TIMEOUT = 120.0

class MessageQueue:
    def __init__(self):
        self._queue: asyncio.Queue[Slot] = asyncio.Queue()

    def reserve(self) -> Slot:
        slot = asyncio.get_running_loop().create_future()
        self._queue.put_nowait(slot)
        return slot

    async def put(self, message: IncomingMessage) -> None:
        slot = self.reserve()
        slot.set_result(message)

    async def worker(self, handler: MessageHandler) -> None:
        while True:
            slot = await self._queue.get()
            try:
                message = await asyncio.wait_for(slot, SLOT_TIMEOUT)
                if message is not None:  # None = слот пропущен (ошибка)
                    await handler(message)
            except asyncio.TimeoutError:
                logger.error("Slot was not filled in %.0fs, skipping", SLOT_TIMEOUT)
            except Exception:
                logger.exception("Failed to process queued message")
            finally:
                self._queue.task_done()
