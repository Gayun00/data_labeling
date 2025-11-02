"""Pydantic 데이터 모델 정의."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class SampleRecord(BaseModel):
    """라벨이 포함된 샘플 데이터."""

    thread_id: str
    summary: str
    message_concat: str
    category: str
    subtopic: Optional[str] = None
    intent: Optional[str] = None
    sentiment: Optional[str] = None
    urgency: Optional[str] = None
    issue_type: Optional[str] = None
    language: Optional[str] = None
    resolution_type: Optional[str] = None
    next_action: Optional[str] = None
    spam: bool = False
    confidence: Optional[float] = Field(default=None, ge=0, le=1)


class ConversationRecord(BaseModel):
    """라벨링이 필요한 신규 상담 스레드."""

    thread_id: str
    created_at: datetime
    channel: Optional[str] = None
    service: Optional[str] = None
    summary: Optional[str] = None
    message_concat: str


class LLMLabel(BaseModel):
    """LLM의 분류 결과."""

    summary: str
    category: str
    subtopic: Optional[str] = None
    intent: Optional[str] = None
    sentiment: Optional[str] = None
    urgency: Optional[str] = None
    issue_type: Optional[str] = None
    language: Optional[str] = None
    resolution_type: Optional[str] = None
    next_action: Optional[str] = None
    spam: bool = False
    confidence: float = Field(ge=0, le=1)
    notes: Optional[str] = None


class LabeledResult(BaseModel):
    """최종 저장용 라벨 결과."""

    conversation: ConversationRecord
    label: LLMLabel
    similar_threads: List[str] = Field(default_factory=list)


class EmbeddingPayload(BaseModel):
    """임베딩 저장을 위한 데이터 구조."""

    id: str
    vector: List[float]
    metadata: dict
