"""End-to-end pipeline for labeling reviews using sample embeddings and LLM."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Mapping, Optional

import pandas as pd

MAX_TEXT_LENGTH = 400
MAX_SAMPLE_PER_REVIEW = 2
MAX_WORKERS = 4

from app.core.config import get_settings
from app.core.embedding_client import EmbeddingClient
from app.core.exceptions import DataValidationError
from app.core.llm_client import LLMClient
from app.core.prompt_builder import build_messages
from app.core.review_utils import prepare_review_records
from app.core.schema import LabeledRecord, LLMLabel, ReviewRecord
from app.core.vector_store import VectorStore


def _truncate(text: str | None) -> str:
    if not text:
        return ""
    return text[:MAX_TEXT_LENGTH]


def _prepare_record(record: ReviewRecord) -> ReviewRecord:
    return record.copy(
        update={
            "message_concat": _truncate(record.message_concat),
            "message_first": _truncate(record.message_first),
            "message_last": _truncate(record.message_last),
        }
    )


def _prepare_sample(sample: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "thread_id": str(sample.get("thread_id", "")),
        "summary": sample.get("summary", ""),
        "category": sample.get("category", ""),
        "subtopic": sample.get("subtopic", ""),
        "intent": sample.get("intent", ""),
        "sentiment": sample.get("sentiment", ""),
        "urgency": sample.get("urgency", ""),
        "issue_type": sample.get("issue_type", ""),
        "language": sample.get("language", ""),
        "resolution_type": sample.get("resolution_type", ""),
        "next_action": sample.get("next_action", ""),
        "message_concat": _truncate(sample.get("message_concat", "")),
    }


def _build_labeled_record(record: ReviewRecord, label: LLMLabel) -> LabeledRecord:
    return LabeledRecord(
        thread_id=record.thread_id,
        created_at=record.created_at,
        channel=record.channel,
        service=record.service,
        user_id_hash=record.user_id_hash,
        message_first=record.message_first,
        message_last=record.message_last,
        message_concat=record.message_concat,
        csat=record.csat,
        csat_comment=record.csat_comment,
        summary=label.summary,
        category=label.category,
        subtopic=label.subtopic,
        intent=label.intent,
        sentiment=label.sentiment,
        urgency=label.urgency,
        issue_type=label.issue_type,
        language=label.language,
        resolution_type=label.resolution_type,
        next_action=label.next_action,
        spam=label.spam,
        confidence=label.confidence,
        evidence_spans=label.evidence_spans,
        notes=label.notes,
        nearest_thread_ids=label.nearest_thread_ids,
        rule_hits=label.rule_hits,
        model_version=label.model_version,
        taxonomy_version=label.taxonomy_version,
    )


def classify_reviews(
    df: pd.DataFrame,
    mapping: Mapping[str, str],
    collection_name: str,
    neighbors_k: int,
) -> list[LabeledRecord]:
    if not collection_name:
        raise DataValidationError("샘플 임베딩 컬렉션 이름이 필요합니다.")

    reviews = prepare_review_records(df, mapping)
    if not reviews:
        raise DataValidationError("라벨링 가능한 리뷰가 없습니다.")

    settings = get_settings()
    embedder = EmbeddingClient()
    store = VectorStore()

    prepared_records: list[ReviewRecord] = []
    texts: list[str] = []
    for record in reviews:
        prepared = _prepare_record(record)
        prepared_records.append(prepared)
        texts.append(prepared.message_concat)

    review_embeddings = embedder.embed_texts(texts)

    retrievals: list[tuple[int, ReviewRecord, list[dict[str, Any]], list[str]]] = []
    n_results = max(neighbors_k, MAX_SAMPLE_PER_REVIEW)
    for index, (record, embedding) in enumerate(zip(prepared_records, review_embeddings)):
        query = store.query(collection_name, embedding, n_results)
        neighbor_ids = query.get("ids", [[]])
        neighbor_metadatas = query.get("metadatas", [[]])
        samples_raw = neighbor_metadatas[0] if neighbor_metadatas else []
        nearest_ids = [str(tid) for tid in (neighbor_ids[0] if neighbor_ids else [])][:MAX_SAMPLE_PER_REVIEW]
        samples_processed = [_prepare_sample(sample) for sample in samples_raw[:MAX_SAMPLE_PER_REVIEW]]
        retrievals.append((index, record, samples_processed, nearest_ids))

    labeled_records: list[Optional[LabeledRecord]] = [None] * len(retrievals)

    def worker(args: tuple[int, ReviewRecord, list[dict[str, Any]], list[str]]):
        idx, record, samples, nearest_ids = args
        llm_client = LLMClient()
        messages = build_messages(
            review=record,
            samples=samples,
            taxonomy_version=settings.taxonomy_version,
            prompt_version=settings.prompt_version,
        )
        response = llm_client.complete_json(messages)
        label = LLMLabel.model_validate(response)
        label.nearest_thread_ids = nearest_ids
        label.model_version = llm_client.primary_model
        label.taxonomy_version = settings.taxonomy_version
        return idx, _build_labeled_record(record, label)

    max_workers = min(MAX_WORKERS, len(retrievals)) or 1
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(worker, payload) for payload in retrievals]
        for future in as_completed(futures):
            idx, labeled = future.result()
            labeled_records[idx] = labeled

    return [record for record in labeled_records if record is not None]
