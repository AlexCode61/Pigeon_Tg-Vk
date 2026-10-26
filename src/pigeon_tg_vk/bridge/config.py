
import os

from dotenv import load_dotenv

load_dotenv()


def get_required_env(name: str) -> str:
    """Return a required environment variable or raise an error."""
    value = os.getenv(name)

    if not value:
        raise ValueError(f"Required environment variable {name} is not set")

    return value


def get_optional_env(name: str, default: str) -> str:
    """Return an environment variable or its default value."""
    return os.getenv(name, default)
