"""Labeling pipeline tying conversations, retrieval, and LLM."""

from __future__ import annotations

import logging
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol, Sequence

from src.models.conversation import Conversation
from src.models.label import LabelRecord, LabelResult, SampleReference
from src.models.sample import SampleLibrary, SampleMatch
from src.retrieval import SimilarityRetriever

logger = logging.getLogger(__name__)


@dataclass
class LabelingResult:
    records: List[LabelRecord]
    failed: List[str]
    errors: Dict[str, str] = field(default_factory=dict)


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
        errors: Dict[str, str] = {}

        for convo in conversations:
            matches = self.retriever.retrieve(convo, library) if library else []

            if self.llm_service is not None:
                try:
                    result = self.llm_service.label(convo, matches, label_schema)
                except Exception as exc:  # pragma: no cover - fallback path
                    logger.exception("Labeling failed for %s", convo.id)
                    result = self._fallback_label(matches)
                    failed.append(convo.id)
                    errors[convo.id] = str(exc)
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

        return LabelingResult(records=records, failed=failed, errors=errors)

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


class LLMBackend(Protocol):
    """Minimal interface for pluggable LLM providers (OpenAI, Hugging Face 등)."""

    def complete(self, messages: Sequence[Dict[str, Any]], model: str, temperature: float) -> str:
        ...


class OpenAIBackend:
    """Default backend using OpenAI Responses API."""

    def __init__(self, client: Optional["OpenAI"] = None) -> None:
        from openai import OpenAI  # type: ignore

        self._client = client or OpenAI()

    def complete(self, messages: Sequence[Dict[str, Any]], model: str, temperature: float) -> str:
        completion = self._client.chat.completions.create(  # type: ignore[attr-defined]
            model=model,
            messages=list(messages),
            temperature=temperature,
        )

        message = completion.choices[0].message
        content = message["content"] if isinstance(message, dict) else message.content  # type: ignore[index]
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: List[str] = []
            for item in content:
                if isinstance(item, dict) and "text" in item:
                    parts.append(str(item.get("text") or ""))
                elif isinstance(item, str):
                    parts.append(item)
            return "\n".join(parts)
        return str(content)


class LLMService:
    """Wrapper that builds prompts and delegates to an LLM backend."""

    def __init__(
        self,
        backend: Optional[LLMBackend] = None,
        model: str = "gpt-4o-mini",
        temperature: float = 0.1,
    ) -> None:
        self.backend = backend or OpenAIBackend()
        self.model = model
        self.temperature = temperature

    def label(
        self,
        conversation: Conversation,
        matches: Sequence[SampleMatch],
        label_schema: Optional[Sequence[str]] = None,
    ) -> LabelResult:
        prompt = self._build_prompt(conversation, matches, label_schema)

        messages: List[Dict[str, Any]] = [
            {
                "role": "system",
                "content": "You classify customer service conversations. Always respond with JSON.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ]

        text = self.backend.complete(messages, model=self.model, temperature=self.temperature)

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
            "You will classify a conversation.\n"
            f"Possible labels: {schema_text}\n"
            "Reference samples:\n"
            f"{sample_text}\n"
            "Conversation transcript:\n"
            f"{conversation_text}\n"
            "Respond with JSON: {\"label_primary\": str, \"label_secondary\": list[str], \"confidence\": number, \"summary\": str, \"reasoning\": str, \"references\": [{\"sample_id\": str, \"label\": str, \"score\": number}]}"
        )
