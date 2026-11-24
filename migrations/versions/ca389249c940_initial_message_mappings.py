"""initial_message_mappings

Revision ID: ca389249c940
Revises: 
Create Date: 2026-11-24 19:24:07.831539

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ca389249c940'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "message_mappings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=False),
        sa.Column("vk_peer_id", sa.BigInteger(), nullable=False),
        sa.Column("vk_message_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "telegram_chat_id",
            "telegram_message_id",
            name="uq_telegram_message",
        )
    )


def downgrade() -> None:
    op.drop_table("message_mappings")
