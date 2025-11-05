"""Dataclasses representing normalized ChannelTalk conversations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional


@dataclass(frozen=True)
class Attachment:
    """Lightweight attachment metadata stored alongside a message."""

    type: str
    url: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class UserProfile:
    id: str
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ManagerProfile:
    id: str
    name: Optional[str] = None
    email: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BotProfile:
    id: str
    name: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)


SenderType = Literal["user", "manager", "bot", "system"]


@dataclass(frozen=True)
class Message:
    """Single utterance inside a conversation."""

    id: str
    conversation_id: str
    sender_type: SenderType
    sender_id: Optional[str]
    created_at: datetime
    text: str
    attachments: List[Attachment] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Participants:
    """Grouped participant metadata for a conversation."""

    user: Optional[UserProfile]
    managers: List[ManagerProfile] = field(default_factory=list)
    bots: List[BotProfile] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Conversation:
    """Canonical representation of a ChannelTalk chat session."""

    id: str
    channel_id: Optional[str]
    created_at: datetime
    closed_at: Optional[datetime]
    participants: Participants
    messages: List[Message]
    meta: Dict[str, Any] = field(default_factory=dict)

    def sorted_messages(self) -> List[Message]:
        """Return messages ordered by timestamp."""
        return sorted(self.messages, key=lambda msg: msg.created_at)
