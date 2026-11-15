import asyncio
import logging

from pigeon_tg_vk.bridge.storage.database import async_session_maker
from pigeon_tg_vk.bridge.storage.repository import delete_old_mappings

logger = logging.getLogger(__name__)


async def run_mapping_cleanup() -> None:
    while True:
        try:
            async with async_session_maker() as session:
                deleted = await delete_old_mappings(session)

            logger.info("Deleted %s expired message mappings", deleted)

        except Exception:
            logger.exception("Failed to clean old message mappings")

        await asyncio.sleep(24 * 60 * 60)