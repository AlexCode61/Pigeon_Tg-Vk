import asyncio
import logging
import os
import certifi

from pigeon_tg_vk.bridge.adapters.telegram_adapter import run_telegram_bot
from pigeon_tg_vk.bridge.adapters.vk_adapter import run_vk_bot
from pigeon_tg_vk.bridge.core.cleanup import run_mapping_cleanup
from pigeon_tg_vk.bridge.core.handler import run_message_worker
from pigeon_tg_vk.bridge.core.logging_config import setup_logging

os.environ["SSL_CERT_FILE"] = certifi.where()

async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    setup_logging()
    await asyncio.gather(run_telegram_bot(), run_vk_bot(),  run_message_worker(), run_mapping_cleanup())


if __name__ == "__main__":
    asyncio.run(main())
