"""Utilities for loading and validating CSV/XLSX datasets."""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Optional, Sequence

import pandas as pd

from app.core.exceptions import DataValidationError
from app.core.schema import ReviewColumnMapping, SampleColumnMapping
from app.core.preprocess import userchat_excel


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

SAMPLE_REQUIRED_FIELDS: set[str] = {
    "thread_id",
    "message_concat",
}

REVIEW_REQUIRED_FIELDS: set[str] = {
    "thread_id",
    "message_concat",
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
    metadata: Mapping[str, Any] = field(default_factory=dict)


def _guess_mapping(columns: Sequence[str], field_names: Iterable[str]) -> dict[str, str]:
    """Infer a column mapping by simple name matching."""
    normalized = {col.lower(): col for col in columns}
    mapping: dict[str, str] = {}
    for field in field_names:
        default = field
        if default in columns:
            chosen = default
        else:
            chosen = normalized.get(default.lower())
        mapping[field] = chosen or ""
    return mapping


def load_sample_dataset(uploaded_file) -> LoadedDataset:
    """Load a labeled sample dataset and infer column mapping."""
    df, metadata = _load_table(uploaded_file)
    mapping = _guess_mapping(df.columns.tolist(), SAMPLE_FIELD_LABELS.keys())
    return LoadedDataset(dataframe=df, inferred_mapping=mapping, metadata=metadata)


def load_review_dataset(uploaded_file) -> LoadedDataset:
    """Load a review dataset and infer column mapping."""
    df, metadata = _load_table(uploaded_file)
    mapping = _guess_mapping(df.columns.tolist(), REVIEW_FIELD_LABELS.keys())
    return LoadedDataset(dataframe=df, inferred_mapping=mapping, metadata=metadata)


def _load_table(uploaded_file) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Read a Streamlit UploadedFile (CSV/XLSX) into a pandas DataFrame."""
    name = (getattr(uploaded_file, "name", "") or "").lower()
    if name.endswith((".xlsx", ".xls")):
        sheets = userchat_excel.read_userchat_workbook(uploaded_file)
        if userchat_excel.is_userchat_workbook(sheets.keys()):
            return userchat_excel.build_userchat_table(sheets), {"source": "userchat_workbook"}
        # Fallback: use the first sheet as-is
        first_sheet = next(iter(sheets.values()))
        if isinstance(first_sheet, pd.DataFrame):
            return first_sheet, {"source": "excel_single_sheet"}
        raise DataValidationError("엑셀에서 데이터를 읽을 수 없습니다.")
    uploaded_file.seek(0)
    buffer = io.BytesIO(uploaded_file.read())
    uploaded_file.seek(0)
    return pd.read_csv(buffer), {"source": "csv"}


@dataclass
class MappingIssues:
    missing_required: list[str]
    missing_optional: list[str]
    duplicates: list[str]


def validate_mapping(
    mapping: Mapping[str, str],
    columns: Sequence[str],
    required_fields: Optional[Iterable[str]] = None,
) -> MappingIssues:
    """Check mapping completeness and uniqueness, separating required and optional fields."""

    required_set = set(required_fields or [])
    missing_required: list[str] = []
    missing_optional: list[str] = []
    seen: dict[str, str] = {}
    duplicates: list[str] = []

    for field, column in mapping.items():
        column = column or ""
        if not column:
            if field in required_set:
                missing_required.append(field)
            else:
                missing_optional.append(field)
            continue
        if column not in columns:
            if field in required_set:
                missing_required.append(field)
            else:
                missing_optional.append(field)
            continue
        previous = seen.get(column)
        if previous and previous != field:
            duplicates.append(column)
        else:
            seen[column] = field

    return MappingIssues(
        missing_required=missing_required,
        missing_optional=missing_optional,
        duplicates=duplicates,
    )


def to_sample_mapping(mapping: Mapping[str, str]) -> SampleColumnMapping:
    """Convert a mapping dict to a SampleColumnMapping."""
    return SampleColumnMapping(**mapping)


def to_review_mapping(mapping: Mapping[str, str]) -> ReviewColumnMapping:
    """Convert a mapping dict to a ReviewColumnMapping."""
    return ReviewColumnMapping(**mapping)
