"""분류용 프롬프트 빌더."""

from __future__ import annotations

from typing import Iterable, Mapping

from .models import ConversationRecord

MAX_SAMPLE_TEXT = 400


def _truncate(text: str) -> str:
    if not text:
        return ""
    return text[:MAX_SAMPLE_TEXT]


def build_prompt(conversation: ConversationRecord, samples: Iterable[Mapping[str, str]]) -> list[dict[str, str]]:
    samples_section = []
    for idx, sample in enumerate(samples, start=1):
        summary = _truncate(sample.get('summary', ''))
        message = _truncate(sample.get('message_concat', ''))
        samples_section.append(
            f"[{idx}] 요약: {summary}
"
            f"카테고리: {sample.get('category', '')} / {sample.get('subtopic', '')}
"
            f"의도: {sample.get('intent', '')} / 감정: {sample.get('sentiment', '')} / 긴급도: {sample.get('urgency', '')}
"
            f"핵심 메시지: {message}"
        )
    samples_text = "

".join(samples_section) if samples_section else "(샘플 없음)"

    user_prompt = (
        f"신규 상담:
{conversation.message_concat}

"
        f"유사 샘플:
{samples_text}

"
        "summary, category, subtopic, intent, sentiment, urgency, issue_type, language, resolution_type, next_action, spam, confidence, evidence_spans, notes 키를 포함한 JSON으로 답변하세요."
    )

    return [
        {"role": "system", "content": "당신은 고객 상담을 분류하는 어시스턴트입니다."},
        {"role": "user", "content": user_prompt},
    ]
