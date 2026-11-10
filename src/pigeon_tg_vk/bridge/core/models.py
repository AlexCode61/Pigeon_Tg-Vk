from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

@dataclass
class MediaAttachment:
    media_type: Literal["photo", "video", "voice", "document", "audio"]
    file_path: Path
    file_name: str | None = None
    mime_type: str | None = None

@dataclass
class IncomingMessage:
    platform: Literal["telegram" , "vk"]
    chat_id: str
    message_id: str
    text: str | None
    sender_id: str | None
    sender_name: str | None
    reply_to_message_id: str | None = None
    additional_message_ids: list[str] = field(default_factory=list)
    attachments: list[MediaAttachment] = field(default_factory=list)

@dataclass
class DeliveryResult:
    message_id: int
    failed_attachments: list[MediaAttachment] = field(default_factory=list)    

@dataclass(frozen=True)
class Target:
    platform: Literal["telegram", "vk"]
    chat_id: str