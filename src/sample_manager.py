"""샘플 데이터 로딩과 임베딩 관리를 담당."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Tuple

import numpy as np
import pandas as pd
from openai import OpenAI

from .models import SampleRecord
from .vector_store import VectorStore


def load_samples(path: Path) -> List[SampleRecord]:
    df = pd.read_csv(path)
    return [SampleRecord(**row._asdict()) for row in df.itertuples(index=False)]


def embed_samples(samples: Iterable[SampleRecord], client: OpenAI, model: str = "text-embedding-3-small") -> Tuple[List[str], List[List[float]], List[dict]]:
    texts = [sample.message_concat for sample in samples]
    response = client.embeddings.create(model=model, input=texts)
    vectors = [item.embedding for item in response.data]
    ids = [sample.thread_id for sample in samples]
    metadatas = [sample.model_dump() for sample in samples]
    return ids, vectors, metadatas


def refresh_vector_store(samples_path: Path, vector_store: VectorStore, client: OpenAI) -> int:
    samples = load_samples(samples_path)
    if not samples:
        return 0
    ids, vectors, metadatas = embed_samples(samples, client)
    vector_store.upsert(ids, vectors, metadatas)
    return len(ids)
