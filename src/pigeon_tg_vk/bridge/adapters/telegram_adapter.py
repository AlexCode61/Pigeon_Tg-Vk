
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message

from pigeon_tg_vk.bridge.config import get_required_env


async def start_handler(message: Message) -> None:
    await message.answer(
        "Привет! Telegram-адаптер Pigeon_Tg-Vk работает."
    )


async def run_telegram_bot() -> None:
    token = get_required_env("TELEGRAM_BOT_TOKEN")

    bot = Bot(token=token)
    dispatcher = Dispatcher()

    dispatcher.message.register(start_handler, CommandStart())

    try:
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()
