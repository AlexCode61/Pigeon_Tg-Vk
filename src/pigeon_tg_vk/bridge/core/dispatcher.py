import logging
from collections.abc import Awaitable, Callable

from pigeon_tg_vk.bridge.core.models import IncomingMessage
from pigeon_tg_vk.bridge.core.router import get_target_platform

logger = logging.getLogger(__name__)

# (chat_id, text) -> None
SendText = Callable[[str, str], Awaitable[None]]

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
        await sender(target.chat_id, message.text)
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