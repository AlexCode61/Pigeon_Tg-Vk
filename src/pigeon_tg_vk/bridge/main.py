
import asyncio

from pigeon_tg_vk.bridge.adapters.telegram_adapter import run_telegram_bot


async def main() -> None:
    await run_telegram_bot()


if __name__ == "__main__":
    asyncio.run(main())
