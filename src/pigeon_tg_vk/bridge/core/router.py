from typing import Literal

from pigeon_tg_vk.bridge.core.models import IncomingMessage

def get_target_platform(message: IncomingMessage) -> Literal["telegram", "vk"]:
    if message.platform == "telegram":
        return "vk"
    if message.platform == "vk":
        return "telegram"