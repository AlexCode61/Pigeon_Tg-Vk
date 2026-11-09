from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pigeon_tg_vk.bridge.storage.models import MessageMapping

async def create_message_mapping(session: AsyncSession, telegram_chat_id: int, telegram_msg_id: int, vk_peer_id: int, vk_msg_id: int) -> MessageMapping:
    messageMapping = MessageMapping(
        telegram_chat_id=telegram_chat_id,
        telegram_message_id=telegram_msg_id,
        vk_peer_id=vk_peer_id,
        vk_message_id=vk_msg_id
    )
    session.add(messageMapping)
    await session.flush()
    return messageMapping

async def  get_by_telegram_message(session: AsyncSession,  telegram_chat_id: int, telegram_msg_id: int) -> MessageMapping | None:
    stmt = select(MessageMapping).where(
        MessageMapping.telegram_message_id == telegram_msg_id,
        MessageMapping.telegram_chat_id == telegram_chat_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

async def  get_by_vk_message(session: AsyncSession, vk_peer_id: int, vk_msg_id: int) -> MessageMapping | None:
    stmt = select(MessageMapping).where(
        MessageMapping.vk_message_id == vk_msg_id,
        MessageMapping.vk_peer_id == vk_peer_id
        ).order_by(MessageMapping.id).limit(1)
    result = await session.execute(stmt)
    return result.scalars().first()