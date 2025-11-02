"""간단한 벡터 저장 및 검색 레이어."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, List, Sequence

import chromadb

DEFAULT_PATH = Path("./data/samples")


class VectorStore:
    """Chroma PersistentClient 래퍼."""

    def __init__(self, persist_path: Path | None = None, collection: str = "samples") -> None:
        path = persist_path or DEFAULT_PATH
        path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(path))
        self._collection = self._client.get_or_create_collection(collection)

    def upsert(self, ids: Sequence[str], embeddings: Sequence[Sequence[float]], metadatas: Sequence[dict[str, Any]]) -> None:
        self._collection.upsert(ids=list(ids), embeddings=list(embeddings), metadatas=list(metadatas))

    def query(self, vector: Sequence[float], top_k: int = 3) -> List[dict[str, Any]]:
        result = self._collection.query(query_embeddings=[list(vector)], n_results=top_k)
        metadatas = result.get("metadatas", [[]])[0]
        ids = result.get("ids", [[]])[0]
        payload: List[dict[str, Any]] = []
        for meta, id_ in zip(metadatas, ids):
            entry = dict(meta)
            entry["thread_id"] = id_
            payload.append(entry)
        return payload

    def delete(self, ids: Iterable[str]) -> None:
        self._collection.delete(ids=list(ids))
