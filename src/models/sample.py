"""Dataclasses for labeled sample management and retrieval."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass(slots=True, frozen=True)
class SampleRecord:
    """Single human-labeled sample stored in the library."""

    sample_id: str
    label_primary: str
    summary_for_embedding: str
    label_secondary: List[str] = field(default_factory=list)
    raw_text: Optional[str] = None
    source_conversation_id: Optional[str] = None
    origin: Optional[str] = None
    created_at: Optional[datetime] = None
    vector_id: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class SampleMatch:
    """Result item returned by the similarity retriever."""

    sample_id: str
    label_primary: str
    score: float
    summary: str
    snippet: Optional[str] = None
    label_secondary: List[str] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)
