import logging
from collections.abc import Awaitable, Callable

from pigeon_tg_vk.bridge.core.models import IncomingMessage, MediaAttachment, DeliveryResult
from pigeon_tg_vk.bridge.core.router import get_target_platform

from pigeon_tg_vk.bridge.storage.database import async_session_maker
from pigeon_tg_vk.bridge.storage.repository import create_message_mapping, get_by_telegram_message, get_by_vk_message

logger = logging.getLogger(__name__)

# (chat_id, text) -> int
SendMessage = Callable[[str, str | None, int | None, list[MediaAttachment]], Awaitable[int | DeliveryResult]]

_senders: dict[str, SendMessage] = {}


def register_sender(platform: str, sender: SendMessage) -> None:
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

    if not message.text and not message.attachments:
        logger.debug("Skipping message without text: %s", message.message_id)
        return

    sender = _senders.get(target.platform)
    if sender is None:
        logger.error("No sender registered for platform=%s", target.platform)
        return

    try:
        reply_mapping = None
        if message.reply_to_message_id is not None:
            async with async_session_maker() as session:
                if message.platform == "telegram":
                    reply_mapping = await get_by_telegram_message(session=session, telegram_chat_id=int(message.chat_id), telegram_msg_id=int(message.reply_to_message_id))
                else:
                    reply_mapping = await get_by_vk_message(session=session, vk_peer_id=int(message.chat_id), vk_msg_id=int(message.reply_to_message_id))

        reply_target_message_id = None
        if reply_mapping is not None:
            if message.platform == "telegram":
                reply_target_message_id = reply_mapping.vk_message_id
            else:
                reply_target_message_id = reply_mapping.telegram_message_id
        
        text = message.text

        if message.sender_name:
            if text:
                text = f"{message.sender_name}: {text}"
            else:
                text = f"{message.sender_name}"

        result = await sender(target.chat_id, text, reply_target_message_id, message.attachments)
        if isinstance(result, DeliveryResult):
            sent_message_id = result.message_id
            failed_attachments = result.failed_attachments
        else:
            sent_message_id = result
            failed_attachments = []
        
        async with async_session_maker() as session:
           async with session.begin():
                if(target.platform == "telegram"):
                    await create_message_mapping(session=session, telegram_chat_id=int(target.chat_id), telegram_msg_id=sent_message_id, vk_peer_id=int(message.chat_id), vk_msg_id=int(message.message_id))              
                else:
                    message_ids = [message.message_id, *message.additional_message_ids]
                    for msg_id in message_ids:
                        await create_message_mapping(session=session, telegram_chat_id=int(message.chat_id), telegram_msg_id=int(msg_id), vk_peer_id=int(target.chat_id), vk_msg_id=sent_message_id)

        if failed_attachments:
            telegram_sender = _senders.get("telegram")

            if telegram_sender is None:
                logger.error("Telegram sender is not registered")
            else:
                for attachment in failed_attachments:
                    filename = attachment.file_name or attachment.file_path.name

                    warning = (
                        f"Файл «{filename}» не был доставлен в VK."
                    )

                    await telegram_sender(
                        message.chat_id,
                        warning,
                        int(message.message_id),
                        [],
                    )
        
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