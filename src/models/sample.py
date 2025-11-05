"""Dataclasses for labeled sample management and retrieval."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional


@dataclass(frozen=True)
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


@dataclass(frozen=True)
class SampleMatch:
    """Result item returned by the similarity retriever."""

    sample_id: str
    label_primary: str
    score: float
    summary: str
    snippet: Optional[str] = None
    label_secondary: List[str] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SampleLibrary:
    """Collection of sample records keyed by id."""

    records: Dict[str, SampleRecord]
    origin: str
    created_at: datetime

    def __iter__(self) -> Iterable[SampleRecord]:
        return iter(self.records.values())

    def __len__(self) -> int:
        return len(self.records)

    def get(self, sample_id: str) -> Optional[SampleRecord]:
        return self.records.get(sample_id)

    @classmethod
    def from_records(cls, records: Iterable[SampleRecord], origin: str) -> "SampleLibrary":
        mapping = {record.sample_id: record for record in records}
        return cls(records=mapping, origin=origin, created_at=datetime.utcnow())
