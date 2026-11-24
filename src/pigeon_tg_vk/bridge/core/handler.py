
import logging

from pigeon_tg_vk.bridge.core.models import IncomingMessage
from pigeon_tg_vk.bridge.core.dispatcher import dispatch_message
from pigeon_tg_vk.bridge.core.queue import MessageQueue, Slot

message_queue = MessageQueue()

logger = logging.getLogger(__name__)

def reserve_slot() -> Slot:
    return message_queue.reserve()

# Заполнить слот; message=None — пропустить. Повторный вызов безопасен.
def resolve_slot(slot: Slot, message: IncomingMessage | None) -> None:
    if not slot.done():
        slot.set_result(message)

async def handle_incoming_message(message: IncomingMessage) -> None:
    logger.info(
        "Core received message: platform=%s, chat_id=%s, "
        "message_id=%s, sender_id=%s",
        message.platform,
        message.chat_id,
        message.message_id,
        message.sender_id,
    )

    await message_queue.put(message)

async def run_message_worker() -> None:
    await message_queue.worker(dispatch_message)