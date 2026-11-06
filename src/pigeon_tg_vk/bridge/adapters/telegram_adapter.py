import logging

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyParameters
from aiogram import F

from pigeon_tg_vk.bridge.config import get_required_env
from pigeon_tg_vk.bridge.core.models import IncomingMessage
from pigeon_tg_vk.bridge.core.handler import handle_incoming_message
from pigeon_tg_vk.bridge.core.dispatcher import register_sender

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def start_handler(message: Message) -> None:
    await message.answer(
        "Лона самая прекрасная девушка в мире"
    )
    logger.info(
        "Start message: chat_type=%s, chat_id=%s",
        message.chat.type,
        message.chat.id,
    )

async def text_handler(message: Message) -> None:
    if message.text is None or message.chat.type not in ("group", "supergroup"):
        return

    incoming = IncomingMessage(
        platform="telegram",
        chat_id=str(message.chat.id),
        message_id=str(message.message_id),
        text=message.text,
        sender_id=(
            str(message.from_user.id)
            if message.from_user is not None
            else None
        ),
        sender_name=(
            str(message.from_user.full_name)
            if message.from_user is not None
            else None
        )
    )

    if message.reply_to_message:
        incoming.reply_to_message_id = str(message.reply_to_message.message_id)    

    await handle_incoming_message(incoming)
    logger.info(
        "Received message: platform=%s, chat_id=%s, "
        "message_id=%s, sender_id=%s, sender_name=%s, text=%s",
        incoming.platform,
        incoming.chat_id,
        incoming.message_id,
        incoming.sender_id,
        incoming.text,
        incoming.sender_name
    )


async def run_telegram_bot() -> None:
    token = get_required_env("TELEGRAM_BOT_TOKEN")

    bot = Bot(token=token)
    
    async def send_to_telegram(chat_id: str, text: str, reply_to_msg_id: int | None = None) -> int:
        reply = (
            ReplyParameters(message_id=reply_to_msg_id)
            if reply_to_msg_id is not None
            else None
            )
        msg = await bot.send_message(chat_id=int(chat_id), text=text, reply_parameters=reply)
        return msg.message_id
    register_sender("telegram", send_to_telegram)
    dispatcher = Dispatcher()

    dispatcher.message.register(start_handler, CommandStart())
    dispatcher.message.register(
        text_handler,
        F.text & ~F.text.startswith("/"),
    )

    try:
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()
