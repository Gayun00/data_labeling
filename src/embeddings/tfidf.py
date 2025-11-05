"""Simple TF-IDF embedder for prototypes and local testing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from sklearn.feature_extraction.text import TfidfVectorizer


@dataclass
class TfidfEmbedder:
    """Embedder that transforms texts into TF-IDF vectors."""

    max_features: int = 512
    ngram_range: tuple[int, int] = (1, 2)
    analyzer: str = "word"

    def __post_init__(self) -> None:
        self._vectorizer = TfidfVectorizer(
            max_features=self.max_features,
            ngram_range=self.ngram_range,
            analyzer=self.analyzer,
        )

    def embed(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        if not texts:
            return []

        matrix = self._vectorizer.fit_transform(texts)
        return matrix.toarray().tolist()
