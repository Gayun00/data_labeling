"""Utilities to ingest labeled samples into the vector store."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping
import pandas as pd

from app.core.embedding_client import EmbeddingClient
from app.core.exceptions import DataValidationError
from app.core.schema import SampleColumnMapping
from app.core.vector_store import VectorStore


@dataclass
class SampleIngestResult:
    count: int


def _safe_get(row: pd.Series, column: str) -> str:
    if not column:
        return ""
    if column not in row:
        return ""
    value = row[column]
    if pd.isna(value):
        return ""
    return str(value)


def _safe_float(row: pd.Series, column: str) -> float | None:
    if not column or column not in row or pd.isna(row[column]):
        return None
    try:
        return float(row[column])
    except (TypeError, ValueError):
        return None


def ingest_samples(df: pd.DataFrame, mapping: Mapping[str, str], collection_name: str) -> SampleIngestResult:
    if df.empty:
        raise DataValidationError("샘플 데이터가 비어 있습니다.")

    column_mapping = SampleColumnMapping(**mapping)
    thread_col = column_mapping.thread_id
    concat_col = column_mapping.message_concat
    if not thread_col or thread_col not in df.columns:
        raise DataValidationError("thread_id 컬럼이 매핑되어야 합니다.")
    if not concat_col or concat_col not in df.columns:
        raise DataValidationError("message_concat 컬럼이 매핑되어야 합니다.")

    texts: list[str] = []
    ids: list[str] = []
    metadatas: list[dict[str, object]] = []

    for _, row in df.iterrows():
        thread_id = _safe_get(row, thread_col)
        if not thread_id:
            continue
        text = _safe_get(row, concat_col)
        if not text:
            fallback_parts = [
                _safe_get(row, column_mapping.message_first),
                _safe_get(row, column_mapping.message_last),
            ]
            text = " || ".join([part for part in fallback_parts if part])
        text = text.strip()
        if not text:
            continue

        ids.append(str(thread_id))
        texts.append(text)
        metadatas.append(
            {
                "thread_id": str(thread_id),
                "summary": _safe_get(row, column_mapping.summary),
                "category": _safe_get(row, column_mapping.category),
                "subtopic": _safe_get(row, column_mapping.subtopic),
                "intent": _safe_get(row, column_mapping.intent),
                "sentiment": _safe_get(row, column_mapping.sentiment),
                "urgency": _safe_get(row, column_mapping.urgency),
                "issue_type": _safe_get(row, column_mapping.issue_type),
                "language": _safe_get(row, column_mapping.language),
                "resolution_type": _safe_get(row, column_mapping.resolution_type),
                "next_action": _safe_get(row, column_mapping.next_action),
                "spam": _safe_get(row, column_mapping.spam).lower() in {"true", "1", "yes"},
                "confidence": _safe_float(row, column_mapping.confidence),
                "evidence_spans": _safe_get(row, column_mapping.evidence_spans),
                "notes": _safe_get(row, column_mapping.notes),
            }
        )

    if not ids:
        raise DataValidationError("샘플 데이터에서 텍스트를 찾지 못했습니다.")

    embed_client = EmbeddingClient()
    vectors = embed_client.embed_texts(texts)

    if len(vectors) != len(ids):
        raise RuntimeError("임베딩 결과 수가 입력 수와 일치하지 않습니다.")

    store = VectorStore()
    store.reset_collection(collection_name)
    store.upsert(collection_name, ids, vectors, metadatas)

    return SampleIngestResult(count=len(ids))
