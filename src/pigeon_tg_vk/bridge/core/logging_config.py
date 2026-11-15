import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
LOG_DIR = PROJECT_ROOT / "logs"

def setup_logging() -> None:
    LOG_DIR.mkdir(exist_ok=True)

    log_format = (
        "%(asctime)s | %(levelname)s | "
        "%(name)s | %(message)s"
    )

    formatter = logging.Formatter(log_format)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        LOG_DIR / "pigeon.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    logging.basicConfig(
        level=logging.INFO,
        handlers=[
            console_handler,
            file_handler,
        ],
        force=True,
    )