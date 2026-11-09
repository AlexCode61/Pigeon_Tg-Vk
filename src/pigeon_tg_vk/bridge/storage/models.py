from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Integer, BigInteger, DateTime, func, UniqueConstraint
from datetime import datetime

from pigeon_tg_vk.bridge.storage.base import Base

class MessageMapping(Base):
    __tablename__ = "message_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    telegram_message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    vk_peer_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    vk_message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "telegram_chat_id",
            "telegram_message_id",
            name="uq_telegram_message",
        ),
    )
