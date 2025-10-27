"""Data schemas used across the labeling pipeline."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class SampleColumnMapping(BaseModel):
    """Maps labeled sample CSV columns to logical field names."""

    thread_id: str = "thread_id"
    created_at: str = "created_at"
    channel: str = "channel"
    service: str = "service"
    user_id_hash: str = "user_id_hash"
    message_first: str = "message_first"
    message_last: str = "message_last"
    message_concat: str = "message_concat"
    csat: str = "csat"
    csat_comment: str = "csat_comment"
    summary: str = "summary"
    category: str = "category"
    subtopic: str = "subtopic"
    intent: str = "intent"
    sentiment: str = "sentiment"
    urgency: str = "urgency"
    issue_type: str = "issue_type"
    language: str = "language"
    resolution_type: str = "resolution_type"
    next_action: str = "next_action"
    spam: str = "spam"
    confidence: str = "confidence"
    evidence_spans: str = "evidence_spans"
    notes: str = "notes"


class SampleRecord(BaseModel):
    """Labeled sample record."""

    thread_id: str
    created_at: datetime
    channel: str
    service: str
    user_id_hash: str
    message_first: str
    message_last: str
    message_concat: str
    csat: Optional[float] = None
    csat_comment: Optional[str] = None
    summary: str
    category: str
    subtopic: str
    intent: str
    sentiment: Literal["positive", "neutral", "negative"]
    urgency: Literal["high", "medium", "low"]
    issue_type: str
    language: Literal["ko", "en", "other"] = "ko"
    resolution_type: str
    next_action: str
    spam: bool
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_spans: Optional[str] = None
    notes: Optional[str] = None


class ReviewColumnMapping(BaseModel):
    """Maps review CSV columns to logical field names."""

    thread_id: str = "thread_id"
    created_at: str = "created_at"
    channel: str = "channel"
    service: str = "service"
    user_id_hash: str = "user_id_hash"
    message_first: str = "message_first"
    message_last: str = "message_last"
    message_concat: str = "message_concat"
    csat: str = "csat"
    csat_comment: str = "csat_comment"


class ReviewRecord(BaseModel):
    """Incoming review record that needs labeling."""

    thread_id: str
    created_at: datetime
    channel: str
    service: str
    user_id_hash: str
    message_first: str
    message_last: str
    message_concat: str
    csat: Optional[float] = None
    csat_comment: Optional[str] = None


class RuleHint(BaseModel):
    """Rule engine suggestion for a review."""

    intent: Optional[str] = None
    category: Optional[str] = None
    subtopic: Optional[str] = None
    urgency: Optional[str] = None
    confidence_boost: float = 0.0
    matched_keywords: list[str] = Field(default_factory=list)


class LLMLabel(BaseModel):
    """Structured output returned by the LLM."""

    summary: str
    category: str
    subtopic: str
    intent: str
    sentiment: str
    urgency: str
    issue_type: str
    language: str
    resolution_type: str
    next_action: str
    spam: bool
    confidence: float
    evidence_spans: Optional[str] = None
    notes: Optional[str] = None
    nearest_thread_ids: list[str] = Field(default_factory=list)
    rule_hits: list[str] = Field(default_factory=list)
    model_version: str = "gpt-4o-mini"
    taxonomy_version: str = "v1"


class LabeledRecord(BaseModel):
    """Merged record with original fields and generated labels."""

    thread_id: str
    created_at: datetime
    channel: str
    service: str
    user_id_hash: str
    message_first: str
    message_last: str
    message_concat: str
    csat: Optional[float] = None
    csat_comment: Optional[str] = None
    summary: str
    category: str
    subtopic: str
    intent: str
    sentiment: str
    urgency: str
    issue_type: str
    language: str
    resolution_type: str
    next_action: str
    spam: bool
    confidence: float
    evidence_spans: Optional[str] = None
    notes: Optional[str] = None
    nearest_thread_ids: list[str] = Field(default_factory=list)
    rule_hits: list[str] = Field(default_factory=list)
    model_version: str
    taxonomy_version: str


class LabelingJobParams(BaseModel):
    """Runtime options for a labeling job."""

    batch_size: int = Field(default=20, ge=1, le=200)
    neighbors_k: int = Field(default=3, ge=1, le=10)
    use_rules: bool = True
    llm_model: str = "gpt-4o-mini"
    llm_backup_model: Optional[str] = "gpt-4.1-mini"
