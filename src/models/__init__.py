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
from .sample import SampleLibrary, SampleMatch, SampleRecord

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
    "SampleLibrary",
    "SampleMatch",
    "SampleRecord",
]
