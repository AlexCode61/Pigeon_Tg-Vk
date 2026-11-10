import logging
import aiohttp
import asyncio
import json
from pathlib import Path
from uuid import uuid4
from filetype import guess

from vkbottle.bot import Bot, Message
from vkbottle_types.objects import MessagesForward
from vkbottle import PhotoMessageUploader, DocMessagesUploader
from vkbottle import VKAPIError

from pigeon_tg_vk.bridge.adapters.host import upload_temp_link
from pigeon_tg_vk.bridge.config import get_required_env
from pigeon_tg_vk.bridge.core.models import DeliveryResult, IncomingMessage, MediaAttachment
from pigeon_tg_vk.bridge.core.handler import handle_incoming_message
from pigeon_tg_vk.bridge.core.dispatcher import register_sender

logger = logging.getLogger(__name__)

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

    #аудио файлы
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

async def photo_vk(url: str) -> MediaAttachment:
    unique_id = uuid4().hex
    project_root = Path(__file__).resolve().parents[4]
    temp_dir = project_root / "temp"

    temp_dir.mkdir(parents=True, exist_ok=True)
    filepath = temp_dir / unique_id

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url=url) as response:
                response.raise_for_status()
                image_data = await response.read()
                filepath.write_bytes(image_data)
                
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
        except aiohttp.ClientError as e:
            logger.error(f"HTTP: {e}")
            raise
        except OSError:
            logger.exception("File error while processing VK photo")
            raise

async def run_vk_bot() -> None:
    token = get_required_env("VK_GROUP_TOKEN")

    bot = Bot(token=token)

    photo_uploader = PhotoMessageUploader(bot.api)
    doc_uploader = DocMessagesUploader(bot.api)

    async def upload_file_with_retry(uploader, path: Path,  peer_id:int, **upload_params) -> str:
        attempt = 0
        delay = 1.0
        max_delay = 30.0
        while True:
            attempt += 1
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
                delay = min(delay * 2, max_delay)

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

                logger.info(
                    "Uploading {item.media_type}: file=%s, size=%s bytes, exists=%s",
                    item.file_path.name,
                    item.file_path.stat().st_size,
                    item.file_path.exists(),
                )
                    
            logger.info(
                "VK upload finished: chat_id=%s, photos_count=%s",
                chat_id,
                len(media),
            )
        finally:
            for item in attachments:
                item.file_path.unlink(missing_ok=True)
            attachment = ",".join(media) if media else None
            msg_id = await bot.api.messages.send(
                    peer_id=int(chat_id),
                    message=text,
                    random_id=0,
                    forward=forward,
                    attachment=attachment
                )
            
        message_info = await bot.api.messages.get_by_id(
            message_ids=[msg_id],
        )

        logger.info(
            "VK sent message IDs: id=%s, conversation_message_id=%s",
            msg_id,
            message_info.items[0].conversation_message_id,
        )

        conversation_message_id = (
            message_info.items[0].conversation_message_id
        )

        return DeliveryResult(
            message_id=conversation_message_id,
            failed_attachments=failed_attachments,
        )

    register_sender("vk", send_to_vk)

    @bot.on.chat_message()
    async def handle_vk_message(message: Message) -> None:
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
        
        users = await bot.api.users.get(user_ids=[message.from_id])
        attachments:list[MediaAttachment] = []

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

                photo = await photo_vk(largest_size.url)
                attachments.append(photo)
        
        incoming = IncomingMessage(
            platform="vk",
            chat_id=str(message.peer_id),
            message_id=str(message.conversation_message_id),
            text=message.text or None,
            sender_id=str(message.from_id),
            reply_to_message_id=(
                str(message.reply_message.conversation_message_id) if message.reply_message is not None and message.reply_message.conversation_message_id is not None else None),
            sender_name=(
                    f"{users[0].first_name} {users[0].last_name}"
                    if users
                    else None
            ),
            attachments=attachments
        )


        logger.info(
            "Received VK message: chat_id=%s, message_id=%s, attachments=%s",
            incoming.chat_id,
            incoming.message_id,
            len(incoming.attachments),
        )

        await handle_incoming_message(incoming)

    logger.info("Starting VK bot polling...")
    await bot.run_polling()
