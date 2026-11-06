import logging

from vkbottle.bot import Bot, Message
from vkbottle_types.objects import MessagesForward

from pigeon_tg_vk.bridge.config import get_required_env
from pigeon_tg_vk.bridge.core.models import IncomingMessage
from pigeon_tg_vk.bridge.core.handler import handle_incoming_message
from pigeon_tg_vk.bridge.core.dispatcher import register_sender

logger = logging.getLogger(__name__)


async def run_vk_bot() -> None:
    token = get_required_env("VK_GROUP_TOKEN")

    bot = Bot(token=token)

    async def send_to_vk(chat_id: str, text: str,  reply_to_message_id: int | None = None) -> int:
        forward = None

        if reply_to_message_id is not None:
            forward = MessagesForward(
                peer_id=int(chat_id),
                conversation_message_ids=[reply_to_message_id],
                is_reply=True
            ).to_raw()
        
        msg_id = await bot.api.messages.send(
            peer_id=int(chat_id),
            message=text,
            random_id=0,
            forward=forward
        )
       
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
            )
        )


        logger.info(
            "Received VK message: chat_id=%s, message_id=%s",
            incoming.chat_id,
            incoming.message_id,
        )

        await handle_incoming_message(incoming)

    logger.info("Starting VK bot polling...")
    await bot.run_polling()
