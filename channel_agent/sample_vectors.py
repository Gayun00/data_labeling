"""
Lightweight vector indexing for sample data (offline-friendly).

Features:
- Builds a simple JSON-based vector store from samples.csv (text, labels).
- Offline "mock" embedding uses a deterministic token hashing vector (no API keys).
- Real embedding option uses OpenAI embeddings if available.
- Search performs cosine similarity over stored vectors.
"""

import json
import os
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - openai not installed
    OpenAI = None  # type: ignore

SAMPLES_DIR = "data/channel/samples"
SAMPLES_FILE = os.path.join(SAMPLES_DIR, "samples.csv")
VECTORS_FILE = os.path.join(SAMPLES_DIR, "sample_vectors.json")


@dataclass
class SampleVector:
    text: str
    labels: List[str]
    vector: List[float]


def _ensure_dir(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)


def _hash_embed(text: str, dim: int = 384) -> np.ndarray:
    """
    Deterministic mock embedding using token hashing.
    Offline-friendly; not semantic but stable.
    """
    vec = np.zeros(dim, dtype=float)
    for token in text.lower().split():
        idx = hash(token) % dim
        vec[idx] += 1.0
    norm = np.linalg.norm(vec)
    return vec if norm == 0 else vec / norm


def _openai_embed(texts: List[str], model: str = "text-embedding-3-small") -> List[np.ndarray]:
    if OpenAI is None:
        raise RuntimeError("openai package is not installed")
    client = OpenAI()
    resp = client.embeddings.create(model=model, input=texts)
    return [np.array(item.embedding, dtype=float) for item in resp.data]


def build_sample_index(use_mock_embeddings: bool = True, model: str = "text-embedding-3-small") -> str:
    import pandas as pd  # local import to avoid hard dependency at import time

    if not os.path.exists(SAMPLES_FILE):
        raise FileNotFoundError(f"샘플 파일이 없습니다: {SAMPLES_FILE}")

    df = pd.read_csv(SAMPLES_FILE).fillna("")
    if "text" not in df.columns:
        raise ValueError("샘플 파일에 'text' 컬럼이 없습니다.")

    records: List[SampleVector] = []

    texts = [str(t) for t in df["text"].tolist()]
    if len(texts) == 0:
        raise ValueError("샘플 데이터가 비어 있습니다. 입력 후 다시 시도하세요.")

    labels_series = df["labels"].fillna("")
    labels_list = [[p for p in str(l).split("|") if p] for l in labels_series]

    if use_mock_embeddings:
        embeds = [_hash_embed(t) for t in texts]
    else:
        embeds = _openai_embed(texts, model=model)

    for text, labs, emb in zip(texts, labels_list, embeds):
        records.append(SampleVector(text=text, labels=labs, vector=emb.tolist()))

    _ensure_dir(VECTORS_FILE)
    with open(VECTORS_FILE, "w", encoding="utf-8") as f:
        json.dump([record.__dict__ for record in records], f, ensure_ascii=False)
    return VECTORS_FILE


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    denom = (np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def search_sample_index(query: str, top_k: int = 5, use_mock_embeddings: bool = True, model: str = "text-embedding-3-small") -> List[Tuple[SampleVector, float]]:
    if not os.path.exists(VECTORS_FILE):
        raise FileNotFoundError("벡터 인덱스가 없습니다. 먼저 인덱스를 빌드하세요.")

    with open(VECTORS_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)
    records = [
        SampleVector(text=item["text"], labels=item.get("labels", []), vector=item["vector"])
        for item in raw
    ]

    if use_mock_embeddings:
        q_vec = _hash_embed(query)
    else:
        q_vec = _openai_embed([query], model=model)[0]

    scored: List[Tuple[SampleVector, float]] = []
    for rec in records:
        sim = _cosine_sim(np.array(rec.vector, dtype=float), q_vec)
        scored.append((rec, sim))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]
