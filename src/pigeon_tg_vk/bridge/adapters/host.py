import asyncio
import logging
from pathlib import Path

import aiohttp

logger = logging.getLogger(__name__)

LITTERBOX_URL = "https://litterbox.catbox.moe/resources/internals/api.php"


class FileHostRejected(Exception):
    """Сервис ответил, но файл не принял (повторять бессмысленно)."""


async def upload_temp_link(
    path: Path,
    filename: str | None = None,
    hours: int = 72,   # допустимо 1, 12, 24, 72
    attempts: int = 3,
) -> str:
    data = path.read_bytes()  # читаем целиком, чтобы не держать открытый хэндл (на Windows мешает unlink)
    timeout = aiohttp.ClientTimeout(total=120)
    delay = 1.0

    for attempt in range(1, attempts + 1):
        try:
            form = aiohttp.FormData()
            form.add_field("reqtype", "fileupload")
            form.add_field("time", f"{hours}h")
            form.add_field("fileToUpload", data, filename=filename or path.name)

            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(LITTERBOX_URL, data=form) as resp:
                    body = (await resp.text()).strip()

            if resp.status != 200 or not body.startswith("https://"):
                raise FileHostRejected(f"status={resp.status}, body={body[:200]}")
            return body

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.warning("File host upload failed (attempt %s/%s): %s", attempt, attempts, e)
            if attempt == attempts:
                raise
            await asyncio.sleep(delay)
            delay *= 2

    raise RuntimeError("unreachable")