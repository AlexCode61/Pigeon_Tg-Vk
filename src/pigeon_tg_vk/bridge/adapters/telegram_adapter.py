import logging
import asyncio

from collections import defaultdict

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Downloadable, Message, ReplyParameters, FSInputFile, InputMediaPhoto
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

media_groups: dict[str, list[Message]] = defaultdict(list)
album_tasks: dict[str, asyncio.Task] = {}

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

async def media_handler(message: Message, bot: Bot) -> None:
    if message.chat.type not in ("group", "supergroup"):
        return
    if message.media_group_id is not None:
        await collect_album(message=message, bot=bot)
        return
    attachment = await media_telegram(message,bot)

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
            message.from_user.full_name
            if message.from_user is not None
            else None
        ),
        reply_to_message_id=(
            str(message.reply_to_message.message_id)
            if message.reply_to_message
            else None
        ),
        attachments=[attachment],
    )

    await handle_incoming_message(incoming)
    logger.info(
        "Received media: platform=%s, chat_id=%s, message_id=%s, file=%s",
        incoming.platform,
        incoming.chat_id,
        incoming.message_id,
        attachment.file_name
        )

async def document_telegram(message: Message, bot: Bot) -> MediaAttachment:
    document = message.document
    filepath = await download_file(document, bot)
    
    return MediaAttachment(
        media_type="document",
        file_path=filepath,
        file_name=document.file_name,
        mime_type=document.mime_type
    )



async def download_file(file: str | Downloadable, bot: Bot) -> Path:
    unique_id = uuid4().hex
    project_root = Path(__file__).resolve().parents[4]
    temp_dir = project_root / "temp"

    temp_dir.mkdir(parents=True, exist_ok=True)
    filepath = temp_dir / unique_id

    await bot.download(file, destination=filepath)

    return filepath


async def photo_telegram(message: Message, bot: Bot) -> MediaAttachment:
    photo = message.photo[-1]

    filepath = await download_file(photo,bot)

    mime = guess(filepath)

    if mime is None or not mime.mime.startswith("image/"):
        logger.error(f"Could not determine the image format")
        raise ValueError("Could not determine the image format")
    
    new_filepath = filepath.with_suffix(f".{mime.extension}")
    filepath = filepath.rename(new_filepath)

    return MediaAttachment(
        media_type="photo",
        file_path=filepath,
        file_name=filepath.name,
        mime_type=mime.mime
    )

async def video_telegram(message: Message, bot: Bot) -> MediaAttachment:
    video = message.video

    filepath = await download_file(video,bot)
    
    mime = guess(filepath)
    if mime is None or not mime.mime.startswith("video/"):
            logger.error(f"Could not determine the video format")
            raise ValueError("Could not determine the video format")
        
    new_filepath = filepath.with_suffix(f".{mime.extension}")
    filepath = filepath.rename(new_filepath)

    return MediaAttachment(
        media_type="video",
        file_path=filepath,
        file_name=video.file_name,
        mime_type=mime.mime
    )

async def audio_telegram(message: Message, bot: Bot) -> MediaAttachment:
    audio = message.audio

    filepath = await download_file(audio, bot)

    mime = guess(filepath)
    if mime is None or not mime.mime.startswith("audio/"):
            logger.error(f"Could not determine the audio format")
            raise ValueError("Could not determine the audio format")
        
    new_filepath = filepath.with_suffix(f".{mime.extension}")
    filepath = filepath.rename(new_filepath)

    return MediaAttachment(
        media_type="audio",
        file_path=filepath,
        file_name=audio.file_name,
        mime_type=mime.mime
    )    

async def collect_album(message: Message, bot: Bot):
    media_group_id = message.media_group_id

    if media_group_id is None:
        return

    media_groups.setdefault(media_group_id, []).append(message)

    task = album_tasks.get(media_group_id)
    if task is not None:
        task.cancel()

    album_tasks[media_group_id] = asyncio.create_task(process_album_after_delay(media_group_id, bot))

async def process_album_after_delay(keys: str, bot: Bot):
    try:
        await asyncio.sleep(0.8)
        messages = media_groups.pop(keys, [])
        if not messages:
            return

        messages.sort(key=lambda msg: msg.message_id)
        first_msg = messages[0]
        attachments: list[MediaAttachment] = []
        additional_message_ids = []
        text: str | None = None
        for index, msg in enumerate(messages):
            attachments.append(await media_telegram(msg, bot))

            if index > 0:
                additional_message_ids.append(str(msg.message_id))

            if text is None and msg.caption is not None:
                text = msg.caption
        
        incoming = IncomingMessage(
                platform="telegram",
                chat_id=str(first_msg.chat.id),
                message_id=str(first_msg.message_id),
                text=text,
                sender_id=(
                    str(first_msg.from_user.id)
                    if first_msg.from_user is not None
                    else None
                ),
                sender_name=(
                    str(first_msg.from_user.full_name)
                    if first_msg.from_user is not None
                    else None
                ),
                reply_to_message_id=(
                    str(first_msg.reply_to_message.message_id) if first_msg.reply_to_message else None
                ),
                additional_message_ids=additional_message_ids,
                attachments=attachments
            )
        await handle_incoming_message(incoming)
        logger.info(
            "Received photos: platform=%s, chat_id=%s, message_id=%s, media_group_id=%s, photos_count=%s",
            incoming.platform,
            incoming.chat_id,
            incoming.message_id,
            keys,
            len(attachments)
            )

    except asyncio.CancelledError:
        raise
    finally:
        if album_tasks.get(keys) is asyncio.current_task():
            album_tasks.pop(keys, None)

async def media_telegram(message: Message, bot: Bot) -> MediaAttachment:
    if message.document is not None:
        return await document_telegram(message=message, bot=bot)
    elif message.photo:
        return await photo_telegram(message=message, bot=bot)
    elif message.video:
        return await video_telegram(message=message, bot=bot)
    elif message.audio:
        return await audio_telegram(message=message, bot=bot)
    raise  ValueError("Unsupported media type in album")

async def run_telegram_bot() -> None:
    token = get_required_env("TELEGRAM_BOT_TOKEN")

    bot = Bot(token=token)
    
    async def send_to_telegram(chat_id: str, text: str | None, reply_to_msg_id: int | None, attachments: list[MediaAttachment]) -> int:
        reply = (
            ReplyParameters(message_id=reply_to_msg_id)
            if reply_to_msg_id is not None
            else None
            )

        photos: list[MediaAttachment] = []

        for item in attachments:
            if item.media_type == "photo":
                photos.append(item)
        
        if photos:
            if len(photos) > 1:
                media = [
                        InputMediaPhoto(media=FSInputFile(photo.file_path), caption=text if index == 0 else None)
                        for index, photo in enumerate(photos)
                    ]
                msg = await bot.send_media_group(chat_id=int(chat_id), media=media, reply_parameters=reply)
                for photo in photos:
                    photo.file_path.unlink(missing_ok=True)
                return msg[0].message_id
            else:
                photo = FSInputFile(photos[0].file_path)
                msg = await bot.send_photo(chat_id=int(chat_id),caption=text, reply_parameters=reply, photo=photo)
                photos[0].file_path.unlink(missing_ok=True)
                return msg.message_id
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
    dispatcher.message.register(partial(media_handler, bot=bot), F.photo | F.video| F.document | F.audio)

    try:
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()
