
import asyncio
import logging

from pigeon_tg_vk.bridge.adapters.telegram_adapter import run_telegram_bot
from pigeon_tg_vk.bridge.adapters.vk_adapter import run_vk_bot


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    await asyncio.gather(run_telegram_bot(), run_vk_bot())


if __name__ == "__main__":
    asyncio.run(main())
