import logging

from pigeon_tg_vk.bridge.core.models import IncomingMessage
from pigeon_tg_vk.bridge.core.router import get_target_platform

logger = logging.getLogger(__name__)

async def dispatch_message(message: IncomingMessage) -> None:
    target_platform = get_target_platform(message)

    logger.info(
        "Dispatching message: source=%s, target=%s, message_id=%s",
        message.platform,
        target_platform,
        message.message_id,
    )