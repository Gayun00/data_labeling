"""간단한 프롬프트 생성 테스트."""

from src.prompt_builder import build_prompt
from src.models import ConversationRecord


def test_build_prompt_structure():
    convo = ConversationRecord(
        thread_id="test-1",
        created_at="2024-01-01T00:00:00Z",
        channel="web",
        service="demo",
        summary="요약",
        message_concat="안녕하세요 고객센터입니다",
    )
    prompt = build_prompt(convo, [])
    assert len(prompt) == 2
    assert prompt[0]["role"] == "system"
    assert "JSON" in prompt[1]["content"]
