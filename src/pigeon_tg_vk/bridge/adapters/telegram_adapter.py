import logging

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyParameters, FSInputFile
from aiogram import F

from pathlib import Path
from uuid import uuid4
from filetype import guess
from functools import partial

from pigeon_tg_vk.bridge.config import get_required_env
from pigeon_tg_vk.bridge.core.models import IncomingMessage, MediaAttachment
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

async def photo_handler(message: Message, bot: Bot) -> None:
    if message.chat.type not in ("group", "supergroup"):
        return

    attachment = await photo_telegram(message=message, bot=bot)
    incoming = IncomingMessage(
        platform="telegram",
        chat_id=str(message.chat.id),
        message_id=str(message.message_id),
        text=message.caption,
        sender_id=(
            str(message.from_user.id)
            if message.from_user is not None
            else None
        ),
        sender_name=(
            str(message.from_user.full_name)
            if message.from_user is not None
            else None
        ),
        reply_to_message_id=(
            str(message.reply_to_message.message_id) if message.reply_to_message else None
        ),
        attachments=[attachment]
    )
    await handle_incoming_message(incoming)
    logger.info(
    "Received photo: platform=%s, chat_id=%s, message_id=%s, file=%s",
    incoming.platform,
    incoming.chat_id,
    incoming.message_id,
    attachment.file_name,
)

async def photo_telegram(message: Message, bot: Bot) -> MediaAttachment:
    photo = message.photo[-1]
    unique_id = uuid4().hex
    project_root = Path(__file__).resolve().parents[4]
    temp_dir = project_root / "temp"

    temp_dir.mkdir(parents=True, exist_ok=True)
    filepath = temp_dir / unique_id
    await bot.download(photo, destination=filepath)

    mime = guess(filepath)

    if mime is None or not mime.mime.startswith("image/"):
        logger.error("Could not determine the image format")
        raise ValueError("Could not determine the image format")
    new_filepath = filepath.with_suffix(f".{mime.extension}")
    filepath.rename(new_filepath)
    filepath = new_filepath
    
    return MediaAttachment(
        media_type="photo",
        file_path=filepath,
        file_name=filepath.name,
        mime_type=mime.mime
    )


async def run_telegram_bot() -> None:
    token = get_required_env("TELEGRAM_BOT_TOKEN")

    bot = Bot(token=token)
    
    async def send_to_telegram(chat_id: str, text: str | None, reply_to_msg_id: int | None, attachments: list[MediaAttachment]) -> int:
        reply = (
            ReplyParameters(message_id=reply_to_msg_id)
            if reply_to_msg_id is not None
            else None
            )

        attachment = None

        for item in attachments:
            if item.media_type == "photo":
                attachment = item
                break
        
        if attachment is not None:
            photo = FSInputFile(attachment.file_path)
            msg = await bot.send_photo(chat_id=int(chat_id),caption=text, reply_parameters=reply, photo=photo)
            attachment.file_path.unlink(missing_ok=True)
        else: 
            msg = await bot.send_message(chat_id=int(chat_id), text=text, reply_parameters=reply)
        return msg.message_id
    
    register_sender("telegram", send_to_telegram)
    dispatcher = Dispatcher()

    dispatcher.message.register(start_handler, CommandStart())
    dispatcher.message.register(
        text_handler,
        F.text & ~F.text.startswith("/"),
    )
    dispatcher.message.register(partial(photo_handler, bot=bot), F.photo)

    try:
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()
