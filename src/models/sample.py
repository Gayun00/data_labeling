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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "label_primary": self.label_primary,
            "summary_for_embedding": self.summary_for_embedding,
            "label_secondary": list(self.label_secondary),
            "raw_text": self.raw_text,
            "source_conversation_id": self.source_conversation_id,
            "origin": self.origin,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "vector_id": self.vector_id,
            "meta": dict(self.meta),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SampleRecord":
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at)
            except ValueError:
                created_at = None
        label_secondary = data.get("label_secondary") or []
        if isinstance(label_secondary, str):
            label_secondary = [item.strip() for item in label_secondary.split(",") if item.strip()]
        return cls(
            sample_id=data["sample_id"],
            label_primary=data["label_primary"],
            summary_for_embedding=data["summary_for_embedding"],
            label_secondary=list(label_secondary),
            raw_text=data.get("raw_text"),
            source_conversation_id=data.get("source_conversation_id"),
            origin=data.get("origin"),
            created_at=created_at,
            vector_id=data.get("vector_id"),
            meta=dict(data.get("meta") or {}),
        )


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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "origin": self.origin,
            "created_at": self.created_at.isoformat(),
            "records": [record.to_dict() for record in self.records.values()],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SampleLibrary":
        origin = data.get("origin") or "persisted"
        created_at_raw = data.get("created_at")
        created_at = datetime.utcnow()
        if isinstance(created_at_raw, str):
            try:
                created_at = datetime.fromisoformat(created_at_raw)
            except ValueError:
                created_at = datetime.utcnow()
        records_data = data.get("records") or []
        if isinstance(records_data, dict):
            records_data = records_data.values()
        records = {item["sample_id"]: SampleRecord.from_dict(item) for item in records_data}
        return cls(records=records, origin=origin, created_at=created_at)

    def merge(self, other: "SampleLibrary") -> "SampleLibrary":
        combined = dict(self.records)
        combined.update(other.records)
        if self.origin == other.origin:
            origin = self.origin
        else:
            origin = "merged"
        return SampleLibrary(records=combined, origin=origin, created_at=datetime.utcnow())
