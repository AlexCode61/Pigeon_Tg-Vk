from dataclasses import dataclass
from typing import Literal

@dataclass
class IncomingMessage:
    platform: Literal["telegram" , "vk"]
    chat_id: str
    message_id: str
    text: str | None
    sender_id: str | None
    sender_name: str | None
#    reply_to_message_id: int | None

@dataclass(frozen=True)
class Target:
    platform: Literal["telegram", "vk"]
    chat_id: str