"""메인 파이프라인 오케스트레이터."""

from __future__ import annotations

from pathlib import Path
from typing import List

import pandas as pd
from openai import OpenAI

from .llm_service import LLMService
from .models import LabeledResult
from .review_classifier import classify_single
from .review_utils import load_conversations
from .sample_manager import refresh_vector_store
from .vector_store import VectorStore


def run_labeling(
    samples_path: Path,
    conversations_path: Path,
    output_path: Path,
    openai_client: OpenAI,
    llm_service: LLMService,
    vector_store: VectorStore,
) -> List[LabeledResult]:
    """샘플과 대화 데이터를 이용해 라벨링을 수행한다."""

    refresh_vector_store(samples_path, vector_store, openai_client)
    conversations = load_conversations(conversations_path)
    results: List[LabeledResult] = []

    for conversation in conversations:
        labeled = classify_single(
            conversation=conversation,
            llm_service=llm_service,
            vector_store=vector_store,
            openai_client=openai_client,
        )
        results.append(labeled)

    rows = []
    for item in results:
        convo_data = item.conversation.model_dump()
        label_data = item.label.model_dump()
        row = {**convo_data}
        for key, value in label_data.items():
            row[f"label_{key}"] = value
        row["similar_threads"] = ";".join(item.similar_threads)
        rows.append(row)

    df = pd.DataFrame(rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    return results
