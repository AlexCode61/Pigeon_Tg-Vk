import logging

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram import F

from pigeon_tg_vk.bridge.config import get_required_env

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def start_handler(message: Message) -> None:
    await message.answer(
        "Привет! Telegram-адаптер Pigeon_Tg-Vk работает."
    )

async def text_handler(message: Message) -> None:
    if message.text is None:
        return
    logger.info(
        "Received text message: chat_id=%s, message_id=%s",
        message.chat.id,
        message.message_id,
    )


async def run_telegram_bot() -> None:
    token = get_required_env("TELEGRAM_BOT_TOKEN")

    bot = Bot(token=token)
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
