import logging
from collections.abc import Awaitable, Callable

from pigeon_tg_vk.bridge.core.models import IncomingMessage
from pigeon_tg_vk.bridge.core.router import get_target_platform

from pigeon_tg_vk.bridge.storage.database import async_session_maker
from pigeon_tg_vk.bridge.storage.repository import create_message_mapping

logger = logging.getLogger(__name__)

# (chat_id, text) -> int
SendText = Callable[[str, str], Awaitable[int]]

_senders: dict[str, SendText] = {}


def register_sender(platform: str, sender: SendText) -> None:
    _senders[platform] = sender


async def dispatch_message(message: IncomingMessage) -> None:
    target = get_target_platform(message)

    if target is None:
        logger.debug(
            "Ignoring message from unbridged chat: platform=%s, chat_id=%s",
            message.platform,
            message.chat_id,
        )
        return

    if not message.text:
        logger.debug("Skipping message without text: %s", message.message_id)
        return

    sender = _senders.get(target.platform)
    if sender is None:
        logger.error("No sender registered for platform=%s", target.platform)
        return

    try:
        sent_message_id = await sender(target.chat_id, message.text)
        async with async_session_maker() as session:
           async with session.begin():
                if(target.platform == "telegram"):
                    await create_message_mapping(session=session, telegram_chat_id=int(target.chat_id), telegram_msg_id=sent_message_id, vk_peer_id=int(message.chat_id), vk_msg_id=int(message.message_id))              
                else:
                    await create_message_mapping(session=session, telegram_chat_id=int(message.chat_id), telegram_msg_id=int(message.message_id), vk_peer_id=int(target.chat_id), vk_msg_id=sent_message_id)
                  
    except Exception:
        logger.exception(
            "Failed to deliver message: source=%s:%s -> target=%s:%s, message_id=%s",
            message.platform,
            message.chat_id,
            target.platform,
            target.chat_id,
            message.message_id,
        )
        return

    logger.info(
        "Delivered message: source=%s:%s -> target=%s:%s, message_id=%s",
        message.platform,
        message.chat_id,
        target.platform,
        target.chat_id,
        message.message_id,
    )