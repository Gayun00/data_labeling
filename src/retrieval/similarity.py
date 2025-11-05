"""Naive similarity retriever using TF-IDF cosine similarity."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.models.conversation import Conversation
from src.models.sample import SampleLibrary, SampleMatch


@dataclass
class SimilarityRetriever:
    """Compute sample similarity scores for a conversation."""

    top_k: int = 5
    min_similarity: float = 0.0
    max_features: int = 1024
    ngram_range: tuple[int, int] = (1, 2)

    def retrieve(self, conversation: Conversation, library: SampleLibrary) -> List[SampleMatch]:
        if library is None or len(library) == 0:
            return []

        records_list = list(library)
        texts = [record.summary_for_embedding for record in records_list]
        if not conversation.messages:
            return []

        convo_text = self._conversation_text(conversation)
        corpus = texts + [convo_text]

        vectorizer = TfidfVectorizer(max_features=self.max_features, ngram_range=self.ngram_range)
        matrix = vectorizer.fit_transform(corpus)

        sample_matrix = matrix[:-1]
        convo_vector = matrix[-1]

        scores = cosine_similarity(convo_vector, sample_matrix)[0]

        if np.isnan(scores).all():
            return []

        top_indices = np.argsort(scores)[::-1]

        matches: List[SampleMatch] = []
        for idx in top_indices[: self.top_k]:
            score = float(scores[idx])
            if score < self.min_similarity:
                continue
            record = records_list[idx]
            matches.append(
                SampleMatch(
                    sample_id=record.sample_id,
                    label_primary=record.label_primary,
                    score=score,
                    summary=record.summary_for_embedding,
                    snippet=record.raw_text,
                    label_secondary=record.label_secondary,
                    meta=record.meta,
                )
            )
        return matches

    @staticmethod
    def _conversation_text(conversation: Conversation) -> str:
        parts: List[str] = []
        for msg in conversation.messages:
            parts.append(f"{msg.sender_type}: {msg.text}")
        return "\n".join(parts)
