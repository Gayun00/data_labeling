"""리뷰 분류 파이프라인."""

from __future__ import annotations

from typing import Iterable, List

from openai import OpenAI

from .models import ConversationRecord, LabeledResult
from .prompt_builder import build_prompt
from .vector_store import VectorStore


def classify_single(conversation: ConversationRecord, llm_service, vector_store: VectorStore) -> LabeledResult:
    samples = vector_store.query([0.0] * 10)
    prompt = build_prompt(conversation, samples)
    label = llm_service.classify(prompt)
    similar_ids = [sample['thread_id'] for sample in samples]
    return LabeledResult(conversation=conversation, label=label, similar_threads=similar_ids)
