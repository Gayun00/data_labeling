"""샘플 데이터 로딩과 임베딩 관리를 담당."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Tuple

import pandas as pd
from openai import OpenAI

from .models import SampleRecord
from .vector_store import VectorStore


def load_samples(path: Path) -> List[SampleRecord]:
    df = pd.read_csv(path)
    records = []
    for payload in df.fillna('').to_dict(orient='records'):
        records.append(SampleRecord(**payload))
    return records


def embed_samples(samples: Iterable[SampleRecord], client: OpenAI, model: str = 'text-embedding-3-small') -> Tuple[List[str], List[List[float]], List[dict]]:
    samples = list(samples)
    if not samples:
        return [], [], []
    texts = [sample.message_concat for sample in samples]
    response = client.embeddings.create(model=model, input=texts)
    vectors = [item.embedding for item in response.data]
    ids = []
    metadatas = []
    for sample in samples:
        ids.append(sample.thread_id)
        meta = sample.model_dump()
        metadatas.append(meta)
    return ids, vectors, metadatas


def refresh_vector_store(samples_path: Path, vector_store: VectorStore, client: OpenAI) -> int:
    samples = load_samples(samples_path)
    if not samples:
        return 0
    ids, vectors, metadatas = embed_samples(samples, client)
    vector_store.upsert(ids, vectors, metadatas)
    return len(ids)
