import logging
import asyncio

from collections import defaultdict

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Animation, Downloadable, InputMediaAudio, InputMediaDocument, InputMediaVideo, MediaUnion, Message, MessageOriginUnion, ReplyParameters, FSInputFile, InputMediaPhoto, Sticker
from aiogram import F

from pylottie_convert import Animation 
from pathlib import Path
from uuid import uuid4
from filetype import guess
from functools import partial

import imageio_ffmpeg
from rlottie_python.rlottie_wrapper import LottieAnimation

from pigeon_tg_vk.bridge.config import get_required_env
from pigeon_tg_vk.bridge.core.models import IncomingMessage, MediaAttachment
from pigeon_tg_vk.bridge.core.handler import reserve_slot, resolve_slot
from pigeon_tg_vk.bridge.core.dispatcher import register_sender


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

media_groups: dict[str, list[Message]] = defaultdict(list)
album_tasks: dict[str, asyncio.Task] = {}
album_slots: dict[str, "asyncio.Future"] = {}
FFMPEG_TIMEOUT = 60

_jobs: set[asyncio.Task] = set()

async def start_handler(message: Message) -> None:
    await message.answer(
        f"id данного чата: {message.chat.id}"
    )
    logger.info(
        "Start message: chat_type=%s, chat_id=%s",
        message.chat.type,
        message.chat.id,
    )

def should_ignore_message(message: Message) -> bool:
    user = message.from_user

    if user is None:
        return False

    return (
        user.is_bot
        and user.username is not None
        and user.username.lower() in "smartspeech_sber_bot"
    )

def spawn(coro) -> None:
    task = asyncio.create_task(coro)
    _jobs.add(task)
    task.add_done_callback(_jobs.discard)

def forward_name_message(origin: MessageOriginUnion) -> str | None:
    if origin.type == "user":
        return origin.sender_user.full_name

    elif origin.type == "hidden_user":
        return origin.sender_user_name

    elif origin.type == "chat":
        return origin.author_signature or origin.chat.title

    elif origin.type == "channel":
        return origin.author_signature or origin.chat.title
    else:
        return None

async def text_handler(message: Message) -> None:
    if should_ignore_message(message):
        logger.info("Ignored message from bot: @%s", message.from_user.username)
        return
    
    logger.info(
        "Text handler triggered: chat_id=%s, message_id=%s, text=%s",
        message.chat.id,
        message.message_id,
        message.text,
    )
    if message.text is None or message.chat.type not in ("group", "supergroup"):
        return
    slot = reserve_slot()
    try:
        if message.forward_origin:
            forward_name = forward_name_message(message.forward_origin)
            text = f"Пересланное сообщение {forward_name}\n{message.text}"
        else:
            text = message.text
        incoming = IncomingMessage(
            platform="telegram",
            chat_id=str(message.chat.id),
            message_id=str(message.message_id),
            text=text,
            sender_id=(
                str(message.from_user.id)
                if message.from_user is not None
                else None
            ),
            sender_name= (
                message.from_user.full_name
                if message.from_user is not None
                else None
            ),
            reply_to_message_id=(
                str(message.reply_to_message.message_id)
                if message.reply_to_message
                else None
            )
        )
        resolve_slot(slot, incoming)

        logger.info(
            "Received message: platform=%s, chat_id=%s, "
            "message_id=%s, sender_id=%s, sender_name=%s, text=%s",
            incoming.platform,
            incoming.chat_id,
            incoming.message_id,
            incoming.sender_id,
            incoming.sender_name,
            incoming.text,
        )
    finally:
        resolve_slot(slot, None)

async def media_handler(message: Message, bot: Bot) -> None:
    if should_ignore_message(message):
        logger.info("Ignored message from bot: @%s", message.from_user.username)
        return
    if message.chat.type not in ("group", "supergroup"):
        return
    if message.media_group_id is not None:
        await collect_album(message=message, bot=bot)
        return
    slot = reserve_slot()
    spawn(media_job(message=message, bot=bot, slot=slot))

async def media_job(message: Message, bot: Bot, slot) -> None:
    try:
        if message.forward_origin:
            forward_name = forward_name_message(message.forward_origin)
            text = f"Пересланное сообщение {forward_name}\n{message.caption}"
        else:
            text = message.text

        attachment = await media_telegram(message,bot)
        incoming = IncomingMessage(
            platform="telegram",
            chat_id=str(message.chat.id),
            message_id=str(message.message_id),
            text=text,
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

        logger.info(
            "Received media: platform=%s, chat_id=%s, message_id=%s, file=%s",
            incoming.platform,
            incoming.chat_id,
            incoming.message_id,
            attachment.file_name
            )
        resolve_slot(slot, incoming)
    finally:
        resolve_slot(slot, None)

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

async def voice_telegram(message: Message, bot: Bot) -> MediaAttachment:
    voice = message.voice

    filepath = await download_file(voice, bot)

    new_filepath = filepath.with_suffix(".ogg")
    filepath = filepath.rename(new_filepath)

    return MediaAttachment(
        media_type="voice",
        file_path=filepath,
        file_name=filepath.name,
        mime_type=voice.mime_type
    )

async def videonote_telegram(message: Message, bot: Bot) -> MediaAttachment:
    video_note = message.video_note

    filepath = await download_file(video_note, bot)

    new_filepath = filepath.with_suffix(".mp4")
    filepath = filepath.rename(new_filepath)

    return MediaAttachment(
        media_type="video",
        file_path=filepath,
        file_name=filepath.name,
        mime_type="video/mp4"
    )

async def webm_to_gif(source: Path, delete_source: bool = True, fps: float = FFMPEG_TIMEOUT) -> Path:
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    destination = source.with_suffix(".gif")

    filter_complex = (
        f"[0:v]fps={fps},"
        "scale=320:-1:flags=lanczos,"
        "format=rgba,split[a][b];"
        "[a]palettegen=reserve_transparent=1[p];"
        "[b][p]paletteuse=alpha_threshold=128"
    )
    
    process = None
    success = False
    try:
        process = await asyncio.create_subprocess_exec(ffmpeg, "-y", "-i", str(source), "-filter_complex", filter_complex, "-loop", "0", str(destination), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise ValueError(stderr.decode(errors="replace"))
        
        success = True
        return destination
    except Exception:
        logger.exception("Failed to convert %s to gif", source)
        destination.unlink(missing_ok=True)
        raise
    finally:
        if process is not None and process.returncode is None:
            process.kill()
            await process.wait()
        if not success:
            destination.unlink(missing_ok=True)
        if delete_source:
            source.unlink(missing_ok=True)

def tgs_to_gif(source: Path, delete_source: bool = True) -> Path:
    destination = source.with_suffix(".gif")
    try:
        with LottieAnimation.from_tgs(str(source)) as animation:
            animation.save_animation(str(destination), fps=15)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        if delete_source:
            source.unlink(missing_ok=True)
    return destination

def sticker_suffix(sticker: Sticker) -> str:
    if sticker.is_animated:
        return ".tgs"
    if sticker.is_video:
        return ".webm"
    return ".webp"

async def sticker_telegram(message: Message, bot: Bot) -> MediaAttachment:
    sticker = message.sticker

    downloaded = await download_file(sticker, bot)
    filepath = downloaded.rename(downloaded.with_suffix(sticker_suffix(sticker)))
                                 
    if sticker.is_video:
        gif_path = await webm_to_gif(source=filepath)
    elif sticker.is_animated:
        gif_path = await asyncio.to_thread(tgs_to_gif, filepath)
    else:
        return MediaAttachment(
            media_type="photo",
            file_path=filepath,
            file_name=filepath.name,
            mime_type="image/webp",
        )

    return MediaAttachment(
        media_type="document",
        file_path=gif_path,
        file_name=gif_path.name,
        mime_type="image/gif",
    )

async def collect_album(message: Message, bot: Bot):
    media_group_id = message.media_group_id

    if media_group_id is None:
        return

    if media_group_id not in album_slots:
        album_slots[media_group_id] = reserve_slot() 

    media_groups[media_group_id].append(message)

    task = album_tasks.get(media_group_id)
    if task is not None:
        task.cancel()

    album_tasks[media_group_id] = asyncio.create_task(process_album_after_delay(media_group_id, bot))

async def process_album_after_delay(key: str, bot: Bot):
    await asyncio.sleep(0.8)

    album_tasks.pop(key, None)
    messages = media_groups.pop(key, [])
    slot = album_slots.pop(key)
    try:

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
        logger.info(
            "Received photos: platform=%s, chat_id=%s, message_id=%s, media_group_id=%s, photos_count=%s",
            incoming.platform,
            incoming.chat_id,
            incoming.message_id,
            key,
            len(attachments)
            )
        resolve_slot(slot, incoming)

    except asyncio.CancelledError:
        raise
    finally:
        if album_tasks.get(key) is asyncio.current_task():
            album_tasks.pop(key, None)
        resolve_slot(slot, None)

async def media_telegram(message: Message, bot: Bot) -> MediaAttachment:
    if message.document is not None:
        return await document_telegram(message=message, bot=bot)
    elif message.photo:
        return await photo_telegram(message=message, bot=bot)
    elif message.video:
        return await video_telegram(message=message, bot=bot)
    elif message.audio:
        return await audio_telegram(message=message, bot=bot)
    elif message.voice:
        return await voice_telegram(message=message, bot=bot)
    elif message.video_note:
        return await videonote_telegram(message=message, bot=bot)
    elif message.sticker:
        return await sticker_telegram(message=message, bot=bot)
    raise  ValueError("Unsupported media type in album")

async def run_telegram_bot() -> None:
    token = get_required_env("TELEGRAM_BOT_TOKEN")

    bot = Bot(token=token)

    async def visual_send(chat_id: str, text: str | None, reply: ReplyParameters | None, attachments: list[MediaAttachment]) -> int:
        if len(attachments) > 1:
            media: list[MediaUnion] = []
            for index, attachment in enumerate(attachments):
                if attachment.media_type == "photo":
                    media.append(InputMediaPhoto(media=FSInputFile(attachment.file_path), caption=text if index == 0 else None))
                if attachment.media_type == "video":
                    media.append(InputMediaVideo(media=FSInputFile(attachment.file_path), caption=text if index == 0 else None))
            msg = await bot.send_media_group(chat_id=int(chat_id), media=media, reply_parameters=reply)
            return msg[0].message_id
        elif len(attachments) == 1:
            item = attachments[0]
            file = FSInputFile(
                item.file_path,
                filename=item.file_name or item.file_path.name
                )
            if item.media_type == "photo":
                msg = await bot.send_photo(chat_id=int(chat_id), photo=file, caption=text, reply_parameters=reply)
            elif item.media_type == "video":
                msg = await bot.send_video(chat_id=int(chat_id), video=file, caption=text, reply_parameters=reply)
            elif item.media_type == "sticker":
                await bot.send_message(chat_id=int(chat_id), text=text, reply_parameters=reply)
                msg = await bot.send_sticker(chat_id=int(chat_id), sticker=file ,reply_parameters=reply)
            return msg.message_id

    async def audio_send(chat_id: str, text: str | None, reply: ReplyParameters | None, attachments: list[MediaAttachment]) -> int:
        if len(attachments) > 1:
            media = [
                    InputMediaAudio(media=FSInputFile(audio.file_path), caption=text)
                    for audio in attachments
                ]
            msg = await bot.send_media_group(chat_id=int(chat_id), media=media, reply_parameters=reply)
            return msg[0].message_id
        elif len(attachments) == 1:
            item = attachments[0]
            file = FSInputFile(
                item.file_path,
                filename=item.file_name or item.file_path.name
                )
            msg = await bot.send_audio(chat_id=int(chat_id),audio=file,caption=text,reply_parameters=reply)
            return msg.message_id

    async def voice_send(chat_id: str, text: str | None, reply: ReplyParameters | None, attachments: list[MediaAttachment]) -> int:
        item = attachments[0]
        file = FSInputFile(
            item.file_path,
            filename=item.file_name or item.file_path.name
            )
        msg = await bot.send_voice(chat_id=int(chat_id),voice=file,caption=text,reply_parameters=reply)
        return msg.message_id
    
    async def document_send(chat_id: str, text: str | None, reply: ReplyParameters | None, attachments: list[MediaAttachment]) -> int:
        if len(attachments) > 1:
            media = [
                    InputMediaDocument(media=FSInputFile(document.file_path), caption=text)
                    for document in attachments
                ]
            msg = await bot.send_media_group(chat_id=int(chat_id), media=media, reply_parameters=reply)
            return msg[0].message_id
        elif len(attachments) == 1:
            item = attachments[0]
            file = FSInputFile(
                item.file_path,
                filename=item.file_name or item.file_path.name
                )
            msg = await bot.send_document(chat_id=int(chat_id), document=file, caption=text, reply_parameters=reply)
            return msg.message_id
    
    async def send_to_telegram(chat_id: str, text: str | None, reply_to_msg_id: int | None, attachments: list[MediaAttachment]) -> int:
        try:
            reply = (
                ReplyParameters(message_id=reply_to_msg_id)
                if reply_to_msg_id is not None
                else None
                )

            if attachments:
                groups = {"visual": [],
                    "audio": [],
                    "document": [],
                    "voice": []}
                first_message_id: int | None = None
            
                for item in attachments:
                    if item.media_type in ("photo", "video", "sticker"):
                        groups["visual"].append(item)
                    elif item.media_type in ("audio", "document", "voice"):
                        groups[item.media_type].append(item)

                for group_type, items in groups.items():
                    if not items:
                        continue

                    if group_type == "visual":
                        msg_id = await visual_send(chat_id=int(chat_id), text=text, reply=reply, attachments=items)
                    elif group_type == "audio":
                        msg_id = await audio_send(chat_id=int(chat_id), text=text, reply=reply, attachments=items)
                    elif group_type == "document":
                        msg_id = await document_send(chat_id=int(chat_id), text=text, reply=reply, attachments=items)
                    elif group_type == "voice":
                        msg_id = await voice_send(chat_id=int(chat_id), text=text, reply=reply, attachments=items)
                    if first_message_id is None:
                        first_message_id = msg_id
                return first_message_id
            else: 
                msg = await bot.send_message(chat_id=int(chat_id), text=text, reply_parameters=reply)
                return msg.message_id
        finally:
            for item in attachments:
                try:
                    item.file_path.unlink(missing_ok=True)
                    logger.info("Temporary file deleted: %s", item.file_path)
                except OSError:
                    logger.exception(
                        "Failed to delete temporary file: %s",
                        item.file_path,
                    )
    
    register_sender("telegram", send_to_telegram)
    dispatcher = Dispatcher()

    dispatcher.message.register(start_handler, CommandStart())
    dispatcher.message.register(
        text_handler,
        F.text & ~F.text.startswith("/"),
    )
    dispatcher.message.register(partial(media_handler, bot=bot), 
                                F.photo | 
                                F.video| 
                                F.document | 
                                F.audio | 
                                F.voice | 
                                F.video_note |
                                F.sticker
                                )

    try:
        await dispatcher.start_polling(bot, handle_as_tasks=False)
    finally:
        await bot.session.close()
