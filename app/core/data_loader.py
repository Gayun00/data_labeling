"""Utilities for loading and validating CSV datasets."""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

import pandas as pd

from app.core.schema import ReviewColumnMapping, SampleColumnMapping


class DataValidationError(Exception):
    """Raised when required columns are missing or invalid."""


SAMPLE_FIELD_LABELS: Mapping[str, str] = {
    "thread_id": "thread_id (스레드 ID)",
    "created_at": "created_at (생성일)",
    "channel": "channel (채널)",
    "service": "service (서비스)",
    "user_id_hash": "user_id_hash (사용자ID 해시)",
    "message_first": "message_first (첫 메시지)",
    "message_last": "message_last (마지막 메시지)",
    "message_concat": "message_concat (핵심 텍스트)",
    "csat": "csat (만족도)",
    "csat_comment": "csat_comment (만족도 코멘트)",
    "summary": "summary (요약)",
    "category": "category (대분류)",
    "subtopic": "subtopic (세부)",
    "intent": "intent (의도)",
    "sentiment": "sentiment (감정)",
    "urgency": "urgency (긴급도)",
    "issue_type": "issue_type (이슈 유형)",
    "language": "language (언어)",
    "resolution_type": "resolution_type (해결 유형)",
    "next_action": "next_action (다음 담당)",
    "spam": "spam (스팸 여부)",
    "confidence": "confidence (확신도)",
    "evidence_spans": "evidence_spans (근거 문구)",
    "notes": "notes (비고)",
}

REVIEW_FIELD_LABELS: Mapping[str, str] = {
    "thread_id": "thread_id (스레드 ID)",
    "created_at": "created_at (생성일)",
    "channel": "channel (채널)",
    "service": "service (서비스)",
    "user_id_hash": "user_id_hash (사용자ID 해시)",
    "message_first": "message_first (첫 메시지)",
    "message_last": "message_last (마지막 메시지)",
    "message_concat": "message_concat (핵심 텍스트)",
    "csat": "csat (만족도)",
    "csat_comment": "csat_comment (만족도 코멘트)",
}


@dataclass
class LoadedDataset:
    """Container for a loaded dataframe and inferred mapping."""

    dataframe: pd.DataFrame
    inferred_mapping: Mapping[str, str]


def _guess_mapping(columns: Sequence[str], field_names: Iterable[str]) -> dict[str, str]:
    """Infer a column mapping by simple name matching."""
    normalized = {col.lower(): col for col in columns}
    mapping: dict[str, str] = {}
    for field in field_names:
        default = field
        chosen = None
        if default in columns:
            chosen = default
        else:
            chosen = normalized.get(default.lower())
        mapping[field] = chosen or ""
    return mapping


def load_sample_dataset(uploaded_file) -> LoadedDataset:
    """Load a labeled sample CSV and infer column mapping."""
    df = _load_csv(uploaded_file)
    mapping = _guess_mapping(df.columns.tolist(), SAMPLE_FIELD_LABELS.keys())
    return LoadedDataset(dataframe=df, inferred_mapping=mapping)


def load_review_dataset(uploaded_file) -> LoadedDataset:
    """Load a review CSV and infer column mapping."""
    df = _load_csv(uploaded_file)
    mapping = _guess_mapping(df.columns.tolist(), REVIEW_FIELD_LABELS.keys())
    return LoadedDataset(dataframe=df, inferred_mapping=mapping)


def _load_csv(uploaded_file) -> pd.DataFrame:
    """Read a Streamlit UploadedFile into a pandas DataFrame."""
    uploaded_file.seek(0)
    buffer = io.BytesIO(uploaded_file.read())
    uploaded_file.seek(0)
    df = pd.read_csv(buffer)
    return df


def validate_mapping(mapping: Mapping[str, str], columns: Sequence[str]) -> tuple[list[str], list[str]]:
    """Check mapping completeness and uniqueness.

    Returns (missing_fields, duplicated_columns).
    """
    missing = [field for field, column in mapping.items() if not column]
    seen: dict[str, str] = {}
    duplicates: list[str] = []
    for field, column in mapping.items():
        if not column:
            continue
        if column not in columns:
            missing.append(field)
            continue
        previous = seen.get(column)
        if previous and previous != field:
            duplicates.append(column)
        else:
            seen[column] = field
    return missing, duplicates


def to_sample_mapping(mapping: Mapping[str, str]) -> SampleColumnMapping:
    """Convert a mapping dict to a SampleColumnMapping."""
    return SampleColumnMapping(**mapping)


def to_review_mapping(mapping: Mapping[str, str]) -> ReviewColumnMapping:
    """Convert a mapping dict to a ReviewColumnMapping."""
    return ReviewColumnMapping(**mapping)
