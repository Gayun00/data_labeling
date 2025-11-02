"""Conversation 전처리 유틸리티."""

from __future__ import annotations

from pathlib import Path
from typing import List

import pandas as pd

from .models import ConversationRecord


def load_conversations(path: Path) -> List[ConversationRecord]:
    df = pd.read_csv(path, parse_dates=["created_at"])
    records = []
    for payload in df.fillna("").to_dict(orient="records"):
        records.append(ConversationRecord(**payload))
    return records
