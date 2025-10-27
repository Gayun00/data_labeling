"""LLM client for labeling responses."""

from __future__ import annotations

import json
from typing import Any, List

import backoff
from openai import OpenAI

from app.core.config import get_settings
from app.core.exceptions import DataValidationError


class LLMClient:
    """Wrapper around OpenAI chat completions with JSON output."""

    def __init__(self) -> None:
        self.settings = get_settings()
        api_key = self.settings.openai_api_key
        if not api_key:
            raise DataValidationError("OPENAI_API_KEY 환경변수가 설정되어 있지 않습니다.")
        self._client = OpenAI(api_key=api_key)
        self.primary_model = self.settings.llm_model
        self.backup_model = self.settings.llm_backup_model

    @backoff.on_exception(backoff.expo, Exception, max_tries=3)
    def _call(self, model: str, messages: List[dict[str, str]]) -> str:
        response = self._client.chat.completions.create(  # type: ignore[attr-defined]
            model=model,
            messages=messages,
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content or ""

    def complete_json(self, messages: List[dict[str, str]]) -> dict[str, Any]:
        models = [self.primary_model]
        if self.backup_model:
            models.append(self.backup_model)
        last_error: Exception | None = None
        for model_name in models:
            try:
                content = self._call(model_name, messages)
                return json.loads(content)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                continue
        raise RuntimeError(f"LLM 호출에 실패했습니다: {last_error}")

