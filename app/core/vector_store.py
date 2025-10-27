"""Persistence layer for sample/review embeddings using ChromaDB."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

import chromadb

from app.core.config import get_settings


class VectorStore:
    """Simple wrapper around a persistent Chroma client."""

    def __init__(self) -> None:
        settings = get_settings()
        path: Path = settings.vector_store_path
        path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(path))

    def reset_collection(self, name: str) -> None:
        try:
            self._client.delete_collection(name)
        except Exception:
            pass

    def _get_collection(self, name: str):
        return self._client.get_or_create_collection(name, metadata={"hnsw:space": "cosine"})

    def upsert(
        self,
        name: str,
        ids: Sequence[str],
        embeddings: Sequence[Sequence[float]],
        metadatas: Sequence[dict[str, Any]],
    ) -> None:
        collection = self._get_collection(name)
        collection.upsert(ids=list(ids), embeddings=list(embeddings), metadatas=list(metadatas))

    def query(
        self,
        name: str,
        embedding: Sequence[float],
        n_results: int,
        where: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        collection = self._get_collection(name)
        return collection.query(query_embeddings=[embedding], n_results=n_results, where=where)
