"""Labeling pipeline tying conversations, retrieval, and LLM."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Sequence

from src.models.conversation import Conversation
from src.models.label import LabelRecord, LabelResult, SampleReference
from src.models.sample import SampleLibrary, SampleMatch
from src.retrieval import SimilarityRetriever


@dataclass
class LabelingResult:
    records: List[LabelRecord]
    failed: List[str]


class LabelingPipeline:
    def __init__(
        self,
        retriever: SimilarityRetriever,
        llm_service: Optional["LLMService"] = None,
    ) -> None:
        self.retriever = retriever
        self.llm_service = llm_service

    def run(
        self,
        conversations: Sequence[Conversation],
        library: Optional[SampleLibrary],
        label_schema: Optional[Sequence[str]] = None,
    ) -> LabelingResult:
        records: List[LabelRecord] = []
        failed: List[str] = []

        for convo in conversations:
            matches = self.retriever.retrieve(convo, library) if library else []

            if self.llm_service is not None:
                try:
                    result = self.llm_service.label(convo, matches, label_schema)
                except Exception:  # pragma: no cover - fallback path
                    result = self._fallback_label(matches)
                    failed.append(convo.id)
            else:
                result = self._fallback_label(matches)

            records.append(
                LabelRecord(
                    conversation_id=convo.id,
                    conversation_version=None,
                    result=result,
                    created_at=datetime.utcnow(),
                )
            )

        return LabelingResult(records=records, failed=failed)

    def _fallback_label(self, matches: Sequence[SampleMatch]) -> LabelResult:
        if matches:
            primary = matches[0].label_primary
            references = [
                SampleReference(sample_id=match.sample_id, score=match.score, label=match.label_primary)
                for match in matches
            ]
        else:
            primary = "unknown"
            references = []

        return LabelResult(
            label_primary=primary,
            label_secondary=[match.label_primary for match in matches[1:3]] if matches else [],
            confidence=matches[0].score if matches else None,
            summary=None,
            reasoning=None,
            references=references,
        )


class LLMService:
    """Very small wrapper for LLM classification."""

    def __init__(self, client: Optional["OpenAI"] = None, model: str = "gpt-4.1-mini", temperature: float = 0.1) -> None:
        from openai import OpenAI  # type: ignore

        self.client = client or OpenAI()
        self.model = model
        self.temperature = temperature

    def label(
        self,
        conversation: Conversation,
        matches: Sequence[SampleMatch],
        label_schema: Optional[Sequence[str]] = None,
    ) -> LabelResult:
        prompt = self._build_prompt(conversation, matches, label_schema)

        completion = self.client.responses.create(  # type: ignore[attr-defined]
            model=self.model,
            input=[
                {
                    "role": "system",
                    "content": "You classify customer service conversations. Always respond with JSON.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=self.temperature,
        )

        try:
            text = completion.output_text  # type: ignore[attr-defined]
        except AttributeError:
            text = completion.choices[0].message["content"]  # type: ignore[index]

        payload = json.loads(text)

        references = [
            SampleReference(
                sample_id=ref.get("sample_id"),
                score=ref.get("score"),
                label=ref.get("label"),
                summary=ref.get("summary"),
            )
            for ref in payload.get("references", [])
        ]

        return LabelResult(
            label_primary=payload.get("label_primary", "unknown"),
            label_secondary=payload.get("label_secondary", []),
            confidence=payload.get("confidence"),
            summary=payload.get("summary"),
            reasoning=payload.get("reasoning"),
            references=references,
        )

    def _build_prompt(
        self,
        conversation: Conversation,
        matches: Sequence[SampleMatch],
        label_schema: Optional[Sequence[str]],
    ) -> str:
        schema_text = ", ".join(label_schema) if label_schema else "unknown"
        conversation_text = "\n".join(
            f"[{msg.created_at.isoformat()}] {msg.sender_type}: {msg.text}" for msg in conversation.messages
        )
        sample_lines = []
        for idx, match in enumerate(matches):
            summary = match.summary or ""
            sample_lines.append(
                f"Sample {idx+1}: label={match.label_primary}, score={match.score:.3f}, summary={summary}"
            )
        sample_text = "\n".join(sample_lines) if sample_lines else "(no reference samples)"
        return (
            "You will classify a conversation.
Possible labels: "
            + schema_text
            + "\nReference samples:\n"
            + sample_text
            + "\nConversation transcript:\n"
            + conversation_text
            + "\nRespond with JSON: {\"label_primary\": str, \"label_secondary\": list[str], \"confidence\": number, \"summary\": str, \"reasoning\": str, \"references\": [{\"sample_id\": str, \"label\": str, \"score\": number}]}"
        )
