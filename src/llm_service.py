"""LLM 호출 래퍼.

실제 OpenAI API 호출을 캡슐화하고, 테스트 편의를 위해 모킹하기 쉬운 구조로 작성한다.
"""

from __future__ import annotations

import logging
from typing import List, Mapping, Optional

from dotenv import load_dotenv
from openai import OpenAI

from .models import LLMLabel

load_dotenv()

LOGGER = logging.getLogger(__name__)


class LLMService:
    """요약 및 분류를 담당하는 LLM 서비스."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini") -> None:
        if api_key is None:
            api_key = OpenAI.api_key  # type: ignore[attr-defined]
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY가 설정되어 있지 않습니다.")
        self._client = OpenAI(api_key=api_key)
        self.model = model

    def summarize(self, conversation: str, max_tokens: int = 256) -> str:
        """대화를 요약한다."""

        prompt = (
            "다음 고객 상담 대화를 2~3문장으로 요약해 주세요."
        )
        LOGGER.debug("Summarize prompt: %s", prompt)
        response = self._client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": conversation},
            ],
            max_output_tokens=max_tokens,
        )
        return response.output[0].content[0].text.strip()  # type: ignore[index]

    def classify(self, prompt_messages: List[Mapping[str, str]]) -> LLMLabel:
        """Few-shot 분류 결과를 JSON 형식으로 반환한다."""

        response = self._client.responses.create(
            model=self.model,
            input=prompt_messages,
            response_format={"type": "json_object"},
        )
        payload = response.output[0].content[0].text  # type: ignore[index]
        LOGGER.debug("LLM raw output: %s", payload)
        return LLMLabel.model_validate_json(payload)
