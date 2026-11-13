from pigeon_tg_vk.bridge.core.models import IncomingMessage, Target
from pigeon_tg_vk.bridge.config import get_required_env

def get_target_platform(message: IncomingMessage) -> Target | None:
    tg_chat = get_required_env("TELEGRAM_CHAT_ID")
    vk_chat = get_required_env("VK_PEER_ID")
    
    if message.platform == "telegram":
        return Target(platform="vk", chat_id=vk_chat)
    if message.platform == "vk":
        return Target(platform="telegram", chat_id=tg_chat)
    return None