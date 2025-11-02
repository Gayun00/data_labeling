"""리뷰 분류 파이프라인."""

from __future__ import annotations

from typing import Iterable, List, Mapping

from openai import OpenAI

from .models import ConversationRecord, LabeledResult
from .prompt_builder import build_prompt
from .vector_store import VectorStore

EMBEDDING_MODEL = "text-embedding-3-small"
TOP_K = 3


def _embed_text(text: str, client: OpenAI) -> List[float]:
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=[text])
    return response.data[0].embedding


def classify_single(
    conversation: ConversationRecord,
    llm_service,
    vector_store: VectorStore,
    openai_client: OpenAI,
    top_k: int = TOP_K,
) -> LabeledResult:
    vector = _embed_text(conversation.message_concat, openai_client)
    samples: List[Mapping[str, str]] = vector_store.query(vector, top_k=top_k)
    prompt = build_prompt(conversation, samples)
    label = llm_service.classify(prompt)
    similar_ids = [sample.get("thread_id", "") for sample in samples]
    return LabeledResult(conversation=conversation, label=label, similar_threads=similar_ids)
