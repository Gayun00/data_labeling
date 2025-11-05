"""Management utilities for human-labeled sample data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Protocol, Sequence
from uuid import uuid4

import pandas as pd

from src.models.sample import SampleLibrary, SampleRecord


class EmbeddingBackend(Protocol):
    """Minimal protocol for embedding services."""

    def embed(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        ...


class SampleVectorStore(Protocol):
    """Protocol describing the vector store operations used for samples."""

    def upsert_samples(
        self, records: Sequence[SampleRecord], embeddings: Sequence[Sequence[float]]
    ) -> None:
        ...


@dataclass(slots=True)
class SampleIngestionResult:
    """Outcome of a sample ingestion run."""

    library: SampleLibrary
    embedded_count: int
    skipped_count: int
    errors: List[str]


class SampleManager:
    """Handles ingestion and optional embedding of labeled sample data."""

    REQUIRED_COLUMNS = {"label_primary", "summary"}
    SECONDARY_SEPARATOR = ","

    def __init__(
        self,
        embedder: Optional[EmbeddingBackend] = None,
        vector_store: Optional[SampleVectorStore] = None,
    ) -> None:
        self._embedder = embedder
        self._vector_store = vector_store

    def ingest_from_csv(
        self,
        path: Path,
        origin: str = "csv",
        auto_embed: bool = True,
    ) -> SampleIngestionResult:
        """Load samples from a CSV file and optionally push them to the vector store."""

        df = self._read_csv(path)
        errors: List[str] = []
        records: List[SampleRecord] = []
        skipped = 0

        for idx, row in enumerate(df.to_dict(orient="records"), start=1):
            try:
                record = self._row_to_record(row, origin=origin)
            except ValueError as exc:
                errors.append(f"row {idx}: {exc}")
                skipped += 1
                continue

            records.append(record)

        library = SampleLibrary.from_records(records, origin=origin)
        embedded = self._maybe_embed(library, auto_embed=auto_embed)

        return SampleIngestionResult(
            library=library,
            embedded_count=embedded,
            skipped_count=skipped,
            errors=errors,
        )

    def _read_csv(self, path: Path) -> pd.DataFrame:
        if not path.exists():
            raise FileNotFoundError(f"샘플 CSV 파일을 찾을 수 없습니다: {path}")

        df = pd.read_csv(path)
        missing = self.REQUIRED_COLUMNS.difference(df.columns)
        if missing:
            raise ValueError(f"필수 컬럼이 없습니다: {', '.join(sorted(missing))}")
        return df

    def _row_to_record(self, row: dict, origin: str) -> SampleRecord:
        label_primary = self._require_str(row.get("label_primary"), "label_primary")
        summary = self._require_str(row.get("summary"), "summary")

        sample_id = self._get_optional_str(row.get("sample_id")) or str(uuid4())
        label_secondary = self._parse_secondary(row.get("label_secondary"))
        raw_text = self._get_optional_str(row.get("raw_text"))
        source_conversation_id = self._get_optional_str(row.get("source_conversation_id"))
        created_at = self._parse_datetime(row.get("created_at"))

        meta = {
            key: value
            for key, value in row.items()
            if key
            not in {
                "sample_id",
                "label_primary",
                "label_secondary",
                "summary",
                "raw_text",
                "source_conversation_id",
                "created_at",
            }
            and not self._is_missing(value)
        }

        return SampleRecord(
            sample_id=sample_id,
            label_primary=label_primary,
            label_secondary=label_secondary,
            summary_for_embedding=summary,
            raw_text=raw_text,
            source_conversation_id=source_conversation_id,
            origin=origin,
            created_at=created_at or datetime.utcnow(),
            vector_id=sample_id,
            meta=meta,
        )

    def _maybe_embed(self, library: SampleLibrary, auto_embed: bool) -> int:
        if not auto_embed or self._embedder is None or self._vector_store is None:
            return 0
        if not library:
            return 0

        texts = [record.summary_for_embedding for record in library]
        embeddings = self._embedder.embed(texts)
        if len(embeddings) != len(texts):
            raise ValueError("임베딩 결과 수가 샘플 수와 일치하지 않습니다.")

        self._vector_store.upsert_samples(list(library), embeddings)
        return len(texts)

    def _parse_secondary(self, value: Optional[object]) -> List[str]:
        if value is None or self._is_missing(value):
            return []
        if isinstance(value, (list, tuple, set)):
            return [self._require_str(item, "label_secondary").strip() for item in value if not self._is_missing(item)]
        if not isinstance(value, str):
            value = str(value)
        items = [item.strip() for item in value.split(self.SECONDARY_SEPARATOR)]
        return [item for item in items if item]

    def _parse_datetime(self, value: Optional[object]) -> Optional[datetime]:
        if value is None or self._is_missing(value):
            return None
        try:
            parsed, _ = pd.to_datetime([value], errors="raise")
            return parsed.to_pydatetime()[0]
        except (ValueError, TypeError) as exc:
            raise ValueError(f"created_at 값을 datetime으로 변환할 수 없습니다: {value}") from exc

    @staticmethod
    def _require_str(value: Optional[object], field: str) -> str:
        if value is None or SampleManager._is_missing(value):
            raise ValueError(f"{field} 값이 비어 있습니다.")
        text = str(value).strip()
        if not text:
            raise ValueError(f"{field} 값이 비어 있습니다.")
        return text

    @staticmethod
    def _get_optional_str(value: Optional[object]) -> Optional[str]:
        if value is None or SampleManager._is_missing(value):
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _is_missing(value: object) -> bool:
        if value is None:
            return True
        if isinstance(value, float) and pd.isna(value):
            return True
        if isinstance(value, str) and not value.strip():
            return True
        return False
