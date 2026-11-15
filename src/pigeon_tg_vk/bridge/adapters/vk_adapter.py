import logging
import mimetypes
import ssl
import aiohttp
import asyncio
import json
import re
import ssl
import certifi

from aiohttp import TCPConnector
from pathlib import Path
from uuid import uuid4
from filetype import guess

from vkbottle.bot import Bot, Message
from vkbottle_types.objects import MessagesForward, MessagesMessage, MessagesMessageAttachment
from vkbottle import PhotoMessageUploader, DocMessagesUploader, VoiceMessageUploader, VKAPIError, API, AiohttpClient

from pigeon_tg_vk.bridge.adapters.host import upload_temp_link
from pigeon_tg_vk.bridge.config import get_required_env
from pigeon_tg_vk.bridge.core.models import DeliveryResult, IncomingMessage, MediaAttachment
from pigeon_tg_vk.bridge.core.handler import reserve_slot, resolve_slot
from pigeon_tg_vk.bridge.core.dispatcher import register_sender

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[4]
TEMP_DIR = PROJECT_ROOT / "temp"

_BAD_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')

UNSUPPORTED_EXTENSIONS = {
    # Исполняемые файлы
    ".exe",
    ".dll",
    ".com",
    ".scr",
    ".msi",
    ".jar",
    ".apk",

    # Скрипты
    ".bat",
    ".cmd",
    ".ps1",
    ".sh",
    ".bash",
    ".py",
    ".js",
    ".vbs",

    # Аудио файлы
    ".mp3", 
    # ".m4a",
     ".wav",
     ".flac",
     ".ogg",
     ".aac",
}

def is_unsupported_document(attachment: MediaAttachment) -> bool:
    filename = attachment.file_name or attachment.file_path.name
    extension = Path(filename).suffix.lower()

    return extension in UNSUPPORTED_EXTENSIONS

def safe_stem(name: str, fallback: str) -> str:
    name = _BAD_CHARS.sub("_", name).strip(" .")
    return name[:100] or fallback

async def download_media(url: str, *, media_type: str, mime_prefix: str | None, stem: str | None = None, ext: str | None = None, session: aiohttp.ClientSession | None = None) -> MediaAttachment:
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    stem = safe_stem(stem or "", uuid4().hex)
    tmp_path = TEMP_DIR / f"{uuid4().hex}.part"

    own_session = session is None
    session = session or aiohttp.ClientSession()
    try:
        async with session.get(url) as response:
            logger.info(
                "VK %s download: status=%s, content_type=%s, content_length=%s",
                media_type,
                response.status,
                response.headers.get("Content-Type"),
                response.headers.get("Content-Length"),
            )
            response.raise_for_status()
            with tmp_path.open("wb") as f:
                async for chunk in response.content.iter_chunked(64 * 1024):
                    f.write(chunk)

        kind = guess(tmp_path)

        if mime_prefix and (kind is None or not kind.mime.startswith(mime_prefix)):
            raise ValueError(f"Could not determine the {media_type} format")

        extension = ext.lstrip(".").lower() if ext else (kind.extension if kind else None)
        mime_type = kind.mime if kind else (mimetypes.guess_type(f"x.{extension}")[0] if extension else None) or "application/octet-stream"

        name = f"{stem}.{extension}" if extension else stem
        final_path = TEMP_DIR / name
        tmp_path.replace(final_path)

        return MediaAttachment(
            media_type=media_type,
            file_path=final_path,
            file_name=final_path.name,
            mime_type=mime_type,
        )
    except aiohttp.ClientError:
        logger.exception("HTTP error while downloading VK %s", media_type)
        raise
    except (OSError, ValueError):
        logger.exception("Error while processing VK %s", media_type)
        raise
    finally:
        tmp_path.unlink(missing_ok=True)
        if own_session:
            await session.close()

async def photo_vk(url: str, session: aiohttp.ClientSession | None = None) -> MediaAttachment:
    return await download_media(url=url, media_type="photo", mime_prefix="image/", session=session)

async def audio_vk(attachment: MessagesMessageAttachment, session: aiohttp.ClientSession | None = None) -> MediaAttachment:
    audio = attachment.audio
    return await download_media(url=audio.url, media_type="audio", mime_prefix="audio/", stem=f"{audio.artist} - {audio.title}" ,session=session)

async def doc_vk(attachment: MessagesMessageAttachment, session: aiohttp.ClientSession | None = None) -> MediaAttachment:
    doc = attachment.doc
    return await download_media(url=doc.url, media_type="document", mime_prefix=None, stem=Path(doc.title).stem, ext=doc.ext, session=session)

async def voice_vk(attachment: MessagesMessageAttachment, session: aiohttp.ClientSession | None = None) -> MediaAttachment:
    voice = attachment.audio_message
    return await download_media(voice.link_ogg or voice.link_mp3, media_type="voice", mime_prefix="audio/", session=session)

async def run_vk_bot() -> None:
    token = get_required_env("VK_GROUP_TOKEN")

    ssl_context = ssl.create_default_context(
        cafile=certifi.where()
    )

    http_client = AiohttpClient(
        connector=TCPConnector(ssl=ssl_context)
    )

    api = API(
        token=token,
        http_client=http_client,
    )

    bot = Bot(api=api)

    photo_uploader = PhotoMessageUploader(bot.api)
    doc_uploader = DocMessagesUploader(bot.api)
    voice_uploader = VoiceMessageUploader(bot.api)

    async def upload_file_with_retry(uploader, path: Path,  peer_id:int, **upload_params) -> str:
        delay = 1.0
        for attempt in range(1, 11):
            try:
                logger.info(
                    "Uploading file: path=%s, exists=%s, size=%s",
                    path,
                    path.exists(),
                    path.stat().st_size if path.exists() else None,
                )
                return await uploader.upload(file_source=str(path), peer_id=peer_id, **upload_params)
            except (json.JSONDecodeError, aiohttp.ClientError, asyncio.TimeoutError):
                logger.warning(
                    "VK file upload failed (attempt %s): file=%s, retry in %.1fs",
                    attempt, path.name, delay,
                )
                await asyncio.sleep(delay + 0.5)
                delay = min(delay * 2, 30.0)

    async def send_to_vk(chat_id: str, text: str | None,  reply_to_message_id: int | None, attachments: list[MediaAttachment]) -> int:
        forward = None

        if reply_to_message_id is not None:
            forward = MessagesForward(
                peer_id=int(chat_id),
                conversation_message_ids=[reply_to_message_id],
                is_reply=True
            ).to_raw()
        
        media = []
        failed_attachments = []
        logger.info(
            "VK upload started: chat_id=%s, attachments_count=%s",
            chat_id,
            len(attachments),
        )
        try:
            def add_line(current: str | None, line: str) -> str:
                return (current + "\n" if current else "") + line
            for item in attachments:
                filename = item.file_name or item.file_path.name
                try:
                    if item.media_type == "photo":
                        logger.info(
                            "Uploading photo: file=%s, size=%s bytes, exists=%s",
                            item.file_path.name,
                            item.file_path.stat().st_size,
                            item.file_path.exists(),
                        )
                        media.append(await upload_file_with_retry(photo_uploader, item.file_path, peer_id=int(chat_id)))
                    elif item.media_type == "document"  or item.media_type == "audio" or item.media_type == "video":
                        if  not is_unsupported_document(item):
                            try:
                                media.append(await upload_file_with_retry(doc_uploader, item.file_path, peer_id=int(chat_id), title=filename or item.file_path.name))
                                continue
                            except VKAPIError:
                                logger.warning("VK rejected file, falling back to link: file=%s", filename, exc_info=True)
                        url = await upload_temp_link(item.file_path, filename)
                        text = add_line(text, f"{filename}: {url}")
                    elif item.media_type == "voice":
                        media.append(await upload_file_with_retry(voice_uploader, item.file_path, peer_id=int(chat_id), title=filename or item.file_path.name))

                    logger.info(
                        "Uploading {item.media_type}: file=%s, size=%s bytes, exists=%s",
                        item.file_path.name,
                        item.file_path.stat().st_size,
                        item.file_path.exists(),
                    )
                except Exception:
                    logger.exception(
                        "Skipping attachment after upload failure: %s",
                        filename,
                    )
                    failed_attachments.append(item)
                    continue
                            
            logger.info(
                "VK upload finished: chat_id=%s, photos_count=%s",
                chat_id,
                len(media),
            )
        finally:
            for item in attachments:
                item.file_path.unlink(missing_ok=True)
            attachment = ",".join(media) if media else None
            resp = await bot.api.messages.send(
                peer_ids=[int(chat_id)],   # peer_ids, а не peer_id
                message=text,
                random_id=0,
                forward=forward,
                attachment=attachment,
            )

        conversation_message_id = resp[0].conversation_message_id

        logger.info(
            "VK sent: message_id=%s, conversation_message_id=%s",
            resp[0].message_id,
            conversation_message_id,
        )

        return DeliveryResult(
            message_id=conversation_message_id,
            failed_attachments=failed_attachments,
        )

    async def create_message(message: Message, vk_message: MessagesMessage, initial_user: str | None = None) -> IncomingMessage:
        
                users = await bot.api.users.get(user_ids=[message.from_id])
                sender_name = f"{users[0].first_name} {users[0].last_name}"
                if initial_user:
                    text = f"Пересланное сообщение {sender_name} \n {message.text or ''}"
                else:
                    text = message.text or None
                attachments:list[MediaAttachment] = []
                async with aiohttp.ClientSession() as session:
                    for attachment in vk_message.attachments:
                        logger.info("Attachment type: %s", attachment.type)
        
                        if attachment.type == "photo":
                            sizes = attachment.photo.sizes
        
                            largest_size = max(
                                sizes,
                                key=lambda size: size.width * size.height,
                            )
        
                            logger.info(
                                "Selected photo size: %sx%s, type=%s",
                                largest_size.width,
                                largest_size.height,
                                largest_size.type,
                            )
        
                            photo = await photo_vk(largest_size.url, session)
                            attachments.append(photo)           
                        elif attachment.type == "video":
                            warning = "Видео не может быть перенаправлено в Telegram."
                            text = f"{text}\n{warning}" if text else warning
                            forward = MessagesForward(
                                peer_id=message.peer_id,
                                conversation_message_ids=[message.conversation_message_id],
                                is_reply=True
                            ).to_raw()
                            await bot.api.messages.send(peer_id=message.peer_id, message=warning, random_id=0, forward=forward)
                        elif attachment.type == "audio":
                            audio = await audio_vk(attachment, session)
                            attachments.append(audio)
                        elif attachment.type == "voice" or attachment.type == "audio_message":
                            voice = await voice_vk(attachment, session)
                            attachments.append(voice)
                        elif attachment.type == "doc":
                            document = await doc_vk(attachment, session)
                            attachments.append(document)
                return IncomingMessage(
                    platform="vk",
                    chat_id=str(message.peer_id),
                    message_id=str(message.conversation_message_id),
                    text=text,
                    sender_id=str(message.from_id),
                    reply_to_message_id=(
                        str(message.reply_message.conversation_message_id) if message.reply_message is not None and message.reply_message.conversation_message_id is not None else None),
                    sender_name=(
                            initial_user
                            if initial_user is not None
                            else sender_name
                    ),
                    attachments=attachments
                )

    @bot.on.chat_message(text="/peerid")
    async def get_peer_id(message: Message):
        await bot.api.messages.send(
            peer_id=message.peer_id,
            message=f"ID этой беседы: {message.peer_id}",
            random_id=0,
        )

    register_sender("vk", send_to_vk)
    @bot.on.chat_message()
    async def handle_vk_message(message: Message) -> None:
        fwds = message.fwd_messages or []
        slots = [reserve_slot() for _ in (fwds or [None])]
        try:
            users = await bot.api.users.get(user_ids=[message.from_id])
            initial_user = f"{users[0].first_name} {users[0].last_name}"

            logger.info(
                "VK message received: peer_id=%s, conversation_message_id=%s, "
                "from_id=%s, attachments=%s",
                message.peer_id,
                message.conversation_message_id,
                message.from_id,
                len(message.attachments),
            )
            history = await bot.api.messages.get_by_id(
                peer_id=message.peer_id,
                cmids=[message.conversation_message_id],
            )

            vk_message = history.items[0]

            logger.info(
                "VK message attachments from API: %s",
                len(vk_message.attachments),
            )
            if fwds:
                for forwarded, slot in zip(fwds, slots):
                    incoming = await create_message(message=forwarded, vk_message=forwarded, initial_user=initial_user)
                    
                    logger.info(
                        "Received VK message: chat_id=%s, message_id=%s, attachments=%s",
                        incoming.chat_id,
                        incoming.message_id,
                        len(incoming.attachments),
                    )
                    resolve_slot(slot, incoming)

            else:
                incoming = await create_message(message=message, vk_message=vk_message)

                logger.info(
                    "Received VK message: chat_id=%s, message_id=%s, attachments=%s",
                    incoming.chat_id,
                    incoming.message_id,
                    len(incoming.attachments),
                )

                resolve_slot(slots[0], incoming)
        finally:
            for s in slots:
                resolve_slot(s, None)
    logger.info("Starting VK bot polling...")
    await bot.run_polling()