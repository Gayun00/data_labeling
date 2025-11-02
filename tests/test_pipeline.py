"""기본 파이프라인 테스트 (스텁)."""

import pytest

from src.models import LLMLabel, ConversationRecord


def test_placeholder():
    """구현 전까지는 True를 유지."""

    assert ConversationRecord  # import sanity
    assert LLMLabel
