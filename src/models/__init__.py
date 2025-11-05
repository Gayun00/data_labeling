"""Shared dataclasses and type definitions for the ChannelTalk labeler."""

from .conversation import (
    Attachment,
    BotProfile,
    Conversation,
    Message,
    Participants,
    UserProfile,
    ManagerProfile,
)
from .label import LabelRecord, LabelResult, SampleReference
from .sample import SampleMatch, SampleRecord

__all__ = [
    "Attachment",
    "BotProfile",
    "Conversation",
    "Message",
    "Participants",
    "UserProfile",
    "ManagerProfile",
    "LabelRecord",
    "LabelResult",
    "SampleReference",
    "SampleMatch",
    "SampleRecord",
]
