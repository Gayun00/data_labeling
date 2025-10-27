"""Helpers for preparing review records prior to labeling."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Mapping

import pandas as pd

from app.core.exceptions import DataValidationError
from app.core.schema import ReviewColumnMapping, ReviewRecord


def _safe_get(row: pd.Series, column: str) -> str:
    if not column or column not in row:
        return ""
    value = row[column]
    if pd.isna(value):
        return ""
    return str(value)


def _parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return pd.to_datetime(value, errors="coerce")
    except Exception:  # noqa: BLE001
        return None


def prepare_review_records(df: pd.DataFrame, mapping: Mapping[str, str]) -> list[ReviewRecord]:
    """Convert a DataFrame and mapping into review records for labeling."""

    if df.empty:
        raise DataValidationError("리뷰 데이터가 비어 있습니다.")

    column_mapping = ReviewColumnMapping(**mapping)

    required_cols = [column_mapping.thread_id, column_mapping.message_concat]
    for col in required_cols:
        if not col or col not in df.columns:
            raise DataValidationError("thread_id와 message_concat은 반드시 매핑되어야 합니다.")

    records: list[ReviewRecord] = []
    for _, row in df.iterrows():
        thread_id = _safe_get(row, column_mapping.thread_id)
        if not thread_id:
            continue
        message_concat = _safe_get(row, column_mapping.message_concat)
        if not message_concat:
            fallback_parts: list[str] = []
            fallback_first = _safe_get(row, getattr(column_mapping, "message_first", ""))
            fallback_last = _safe_get(row, getattr(column_mapping, "message_last", ""))
            fallback_parts.extend(part for part in [fallback_first, fallback_last] if part)
            message_concat = " || ".join(fallback_parts)
        if not message_concat:
            continue

        created_at = None
        if column_mapping.created_at and column_mapping.created_at in df.columns:
            created_at = _parse_datetime(_safe_get(row, column_mapping.created_at))

        csat_value = _safe_get(row, column_mapping.csat)
        csat = None
        if csat_value:
            try:
                csat = float(csat_value)
            except ValueError:
                csat = None

        record = ReviewRecord(
            thread_id=str(thread_id),
            created_at=created_at or datetime.utcnow(),
            channel=_safe_get(row, column_mapping.channel),
            service=_safe_get(row, column_mapping.service),
            user_id_hash=_safe_get(row, column_mapping.user_id_hash),
            message_first=_safe_get(row, column_mapping.message_first),
            message_last=_safe_get(row, column_mapping.message_last),
            message_concat=message_concat,
            csat=csat,
            csat_comment=_safe_get(row, column_mapping.csat_comment),
        )
        records.append(record)

    if not records:
        raise DataValidationError("라벨링 가능한 리뷰 텍스트를 찾지 못했습니다.")

    return records
