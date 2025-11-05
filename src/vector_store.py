"""Minimal in-memory vector store placeholder."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence
from uuid import uuid4

from src.models.sample import SampleRecord


@dataclass(slots=True, frozen=True)
class SampleVectorEntry:
    sample_id: str
    embedding: List[float]
    record: SampleRecord
    vector_id: str


class VectorStore:
    """A lightweight vector store for prototypes and tests."""

    def __init__(self) -> None:
        self._sample_vectors: Dict[str, SampleVectorEntry] = {}

    def upsert_samples(
        self, records: Sequence[SampleRecord], embeddings: Sequence[Sequence[float]]
    ) -> None:
        if len(records) != len(embeddings):
            raise ValueError("records와 embeddings 수가 일치해야 합니다.")

        for record, embedding in zip(records, embeddings):
            vector_id = record.vector_id or record.sample_id or str(uuid4())
            entry = SampleVectorEntry(
                sample_id=record.sample_id,
                vector_id=vector_id,
                record=record,
                embedding=[float(x) for x in embedding],
            )
            self._sample_vectors[vector_id] = entry

    def get_sample_vector(self, vector_id: str) -> Optional[SampleVectorEntry]:
        return self._sample_vectors.get(vector_id)

    def list_sample_vectors(self) -> Iterable[SampleVectorEntry]:
        return self._sample_vectors.values()
