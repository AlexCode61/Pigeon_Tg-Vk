from dataclasses import dataclass
from typing import Literal

@dataclass
class IncomingMessage:
    platform: Literal["telegram" , "vk"]
    chat_id: str
    message_id: str
    text: str | None
    sender_id: str | None