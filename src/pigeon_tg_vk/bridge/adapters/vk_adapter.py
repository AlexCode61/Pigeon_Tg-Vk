import logging
import aiohttp
from pathlib import Path
from uuid import uuid4
from filetype import guess

from vkbottle.bot import Bot, Message
from vkbottle_types.objects import MessagesForward
from vkbottle import PhotoMessageUploader

from pigeon_tg_vk.bridge.config import get_required_env
from pigeon_tg_vk.bridge.core.models import IncomingMessage, MediaAttachment
from pigeon_tg_vk.bridge.core.handler import handle_incoming_message
from pigeon_tg_vk.bridge.core.dispatcher import register_sender

logger = logging.getLogger(__name__)

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

    async def send_to_vk(chat_id: str, text: str | None,  reply_to_message_id: int | None, attachments: list[MediaAttachment]) -> int:
        forward = None

        if reply_to_message_id is not None:
            forward = MessagesForward(
                peer_id=int(chat_id),
                conversation_message_ids=[reply_to_message_id],
                is_reply=True
            ).to_raw()
        
        media = []
        for item in attachments:
            if item.media_type == "photo":
                media.append(await photo_uploader.upload(file_source=item.file_path.read_bytes(), peer_id=int(chat_id)))
        
        attachment = ",".join(media) if media else None
        msg_id = await bot.api.messages.send(
                peer_id=int(chat_id),
                message=text,
                random_id=0,
                forward=forward,
                attachment=attachment
            )

        for item in attachments:
            if item.media_type == "photo":
                item.file_path.unlink(missing_ok=True)
            
        message_info = await bot.api.messages.get_by_id(
            message_ids=[msg_id],
        )

        logger.info(
            "VK sent message IDs: id=%s, conversation_message_id=%s",
            msg_id,
            message_info.items[0].conversation_message_id,
        )

        return message_info.items[0].conversation_message_id

    register_sender("vk", send_to_vk)

    @bot.on.chat_message()
    async def handle_vk_message(message: Message) -> None:
        users = await bot.api.users.get(user_ids=[message.from_id])
        attachments:list[MediaAttachment] = []

        for attachment in message.attachments:
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
            "Received VK message: chat_id=%s, message_id=%s",
            incoming.chat_id,
            incoming.message_id,
        )

        await handle_incoming_message(incoming)

    logger.info("Starting VK bot polling...")
    await bot.run_polling()
