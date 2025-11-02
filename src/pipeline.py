"""메인 파이프라인 오케스트레이터."""

from __future__ import annotations

from pathlib import Path
from typing import List

import pandas as pd
from openai import OpenAI

from .llm_service import LLMService
from .models import ConversationRecord, LabeledResult
from .sample_manager import refresh_vector_store
from .vector_store import VectorStore


def prepare_conversations(path: Path) -> List[ConversationRecord]:
    df = pd.read_csv(path, parse_dates=["created_at"])
    return [ConversationRecord(**row._asdict()) for row in df.itertuples(index=False)]


def run_labeling(
    samples_path: Path,
    conversations_path: Path,
    output_path: Path,
    openai_client: OpenAI,
    llm_service: LLMService,
    vector_store: VectorStore,
) -> List[LabeledResult]:
    refresh_vector_store(samples_path, vector_store, openai_client)
    conversations = prepare_conversations(conversations_path)
    results: List[LabeledResult] = []
    for convo in conversations:
        prompt = [
            {"role": "system", "content": "다음 상담을 요약하고 분류하세요."},
            {"role": "user", "content": convo.message_concat},
        ]
        label = llm_service.classify(prompt)
        record = LabeledResult(conversation=convo, label=label)
        results.append(record)
    df = pd.DataFrame([r.model_dump() for r in results])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    return results
