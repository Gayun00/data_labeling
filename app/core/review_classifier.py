"""End-to-end pipeline for labeling reviews using sample embeddings and LLM."""

from __future__ import annotations

from typing import Mapping

import pandas as pd

from app.core.config import get_settings
from app.core.embedding_client import EmbeddingClient
from app.core.exceptions import DataValidationError
from app.core.llm_client import LLMClient
from app.core.prompt_builder import build_messages
from app.core.review_utils import prepare_review_records
from app.core.schema import LabeledRecord, LLMLabel
from app.core.vector_store import VectorStore


def classify_reviews(
    df: pd.DataFrame,
    mapping: Mapping[str, str],
    collection_name: str,
    neighbors_k: int,
) -> list[LabeledRecord]:
    if not collection_name:
        raise DataValidationError("샘플 임베딩 컬렉션 이름이 필요합니다.")

    reviews = prepare_review_records(df, mapping)
    settings = get_settings()

    embedder = EmbeddingClient()
    store = VectorStore()
    llm = LLMClient()

    texts = [record.message_concat for record in reviews]
    review_embeddings = embedder.embed_texts(texts)

    labeled_records: list[LabeledRecord] = []
    for record, embedding in zip(reviews, review_embeddings):
        query = store.query(collection_name, embedding, neighbors_k)
        neighbor_ids = query.get("ids", [[]])
        neighbor_metadatas = query.get("metadatas", [[]])
        samples = neighbor_metadatas[0] if neighbor_metadatas else []
        nearest_ids = neighbor_ids[0] if neighbor_ids else []

        messages = build_messages(
            review=record,
            samples=samples,
            taxonomy_version=settings.taxonomy_version,
            prompt_version=settings.prompt_version,
        )

        llm_response = llm.complete_json(messages)
        label = LLMLabel.model_validate(llm_response)
        label.nearest_thread_ids = [str(tid) for tid in nearest_ids]
        label.model_version = llm.primary_model
        label.taxonomy_version = settings.taxonomy_version

        labeled_records.append(
            LabeledRecord(
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
        )

    return labeled_records
