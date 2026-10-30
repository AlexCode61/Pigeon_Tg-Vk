
import logging

from pigeon_tg_vk.bridge.core.models import IncomingMessage
from pigeon_tg_vk.bridge.core.dispatcher import dispatch_message

logger = logging.getLogger(__name__)

async def handle_incoming_message(message: IncomingMessage) -> None:
    await dispatch_message(message)

    logger.info(
        "Core received message: platform=%s, chat_id=%s, "
        "message_id=%s, sender_id=%s, text=%s",
        message.platform,
        message.chat_id,
        message.message_id,
        message.sender_id,
        message.text,
    )
