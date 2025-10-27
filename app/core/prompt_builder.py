"""Prompt construction utilities for the labeling LLM."""

from __future__ import annotations

from typing import Any, Sequence

from app.core.schema import ReviewRecord


def build_messages(
    review: ReviewRecord,
    samples: Sequence[dict[str, Any]],
    taxonomy_version: str,
    prompt_version: str,
) -> list[dict[str, str]]:
    system_prompt = (
        "당신은 고객 상담 스레드를 분류하는 어시스턴트입니다. "
        "제공된 샘플과 동일한 라벨 체계를 사용해 신규 스레드의 요약과 라벨을 결정하세요. "
        "항상 JSON 형식으로 답변하고, 지정된 키만 사용하세요."
    )

    sample_lines: list[str] = []
    for idx, sample in enumerate(samples, start=1):
        sample_lines.append(
            "\n".join(
                [
                    f"[{idx}] thread_id: {sample.get('thread_id', '')}",
                    f"요약: {sample.get('summary', '')}",
                    f"카테고리: {sample.get('category', '')} / {sample.get('subtopic', '')}",
                    f"의도: {sample.get('intent', '')} / 감정: {sample.get('sentiment', '')} / 긴급도: {sample.get('urgency', '')}",
                    f"해결유형: {sample.get('resolution_type', '')} / 다음 담당: {sample.get('next_action', '')}",
                    f"핵심 메시지: {sample.get('message_concat', '')}",
                ]
            )
        )

    samples_text = "\n\n".join(sample_lines) if sample_lines else "(관련 샘플 없음)"

    review_text = (
        f"thread_id: {review.thread_id}\n"
        f"채널: {review.channel} / 서비스: {review.service}\n"
        f"사용자 메세지 요약: {review.message_concat}\n"
    )

    user_prompt = (
        f"[taxonomy_version={taxonomy_version}, prompt_version={prompt_version}]\n"
        "다음은 유사한 샘플과 신규 상담 스레드입니다.\n"
        "샘플을 참고해 신규 스레드의 요약과 라벨을 JSON으로 출력하세요.\n"
        "출력 형식 예시:\n"
        "{""summary"": ""..."", ""category"": ""..."", ""subtopic"": ""..."", ""intent"": ""..."", ""sentiment"": ""..."", ""urgency"": ""..."", ""issue_type"": ""..."", ""language"": ""..."", ""resolution_type"": ""..."", ""next_action"": ""..."", ""spam"": false, ""confidence"": 0.85, ""evidence_spans"": ""..."", ""notes"": ""...""}"\n"
        "confidence는 0~1 사이 실수로 제공하세요.\n"
        "유사 샘플:\n"
        f"{samples_text}\n\n"
        "신규 스레드:\n"
        f"{review_text}\n"
        "JSON만 출력하세요."
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

