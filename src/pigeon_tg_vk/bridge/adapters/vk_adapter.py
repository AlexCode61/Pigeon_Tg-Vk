
import logging

from vkbottle.bot import Bot, Message

from pigeon_tg_vk.bridge.config import get_required_env
from pigeon_tg_vk.bridge.core.models import IncomingMessage
from pigeon_tg_vk.bridge.core.handler import handle_incoming_message

logger = logging.getLogger(__name__)


async def run_vk_bot() -> None:
    token = get_required_env("VK_GROUP_TOKEN")
    bot = Bot(token=token)

    @bot.on.chat_message()
    async def handle_vk_message(message: Message) -> None:
        incoming = IncomingMessage(
            platform="vk",
            chat_id=str(message.peer_id),
            message_id=str(message.id),
            text=message.text or None,
            sender_id=str(message.from_id),
        )

        logger.info(
            "Received VK message: chat_id=%s, message_id=%s",
            incoming.chat_id,
            incoming.message_id,
        )

        await handle_incoming_message(incoming)

    logger.info("Starting VK bot polling...")
    await bot.run_polling()
