"""Wrapper around OpenAI embedding API with batching and retries."""

from __future__ import annotations

from typing import Iterable, List

import backoff
from openai import OpenAI

from app.core.config import get_settings
from app.core.exceptions import DataValidationError


class EmbeddingClient:
    """Simple embedding client that batches requests to OpenAI."""

    def __init__(self) -> None:
        self.settings = get_settings()
        api_key = self.settings.openai_api_key
        if not api_key:
            raise DataValidationError("OPENAI_API_KEY 환경변수가 설정되어 있지 않습니다.")
        self._client = OpenAI(api_key=api_key)
        self.model = self.settings.embedding_model

    @backoff.on_exception(backoff.expo, Exception, max_tries=5)
    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        response = self._client.embeddings.create(model=self.model, input=texts)
        return [item.embedding for item in response.data]

    def embed_texts(self, texts: Iterable[str]) -> List[List[float]]:
        batch_size = 100
        embeddings: list[list[float]] = []
        batch: list[str] = []
        for text in texts:
            batch.append(text)
            if len(batch) >= batch_size:
                embeddings.extend(self._embed_batch(batch))
                batch = []
        if batch:
            embeddings.extend(self._embed_batch(batch))
        return embeddings
