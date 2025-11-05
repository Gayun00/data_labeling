"""Dataclasses describing label outputs and references."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass(slots=True, frozen=True)
class SampleReference:
    """Reference to a sample used during labeling."""

    sample_id: str
    score: Optional[float] = None
    label: Optional[str] = None
    summary: Optional[str] = None


@dataclass(slots=True, frozen=True)
class LabelResult:
    """Structured response from the LLM labeler."""

    label_primary: str
    label_secondary: List[str] = field(default_factory=list)
    confidence: Optional[float] = None
    summary: Optional[str] = None
    reasoning: Optional[str] = None
    references: List[SampleReference] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class LabelRecord:
    """Persisted label outcome for a conversation."""

    conversation_id: str
    conversation_version: Optional[str]
    result: LabelResult
    created_at: datetime
