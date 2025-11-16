import json
import logging
from typing import Any, Dict, List, Optional

from openai import OpenAI

from .channel_api import ChannelTalkClient
from .config import OpenAIConfig

logger = logging.getLogger(__name__)


DEFAULT_INSTRUCTIONS = (
    "주어진 상담 대화 메시지를 분석하여 핵심 요약과 라벨을 반환하세요. "
    "휴대폰번호, 계좌번호, 주소 등 개인정보는 '***'로 마스킹하세요. "
    "결과는 summary, labels 배열, emotion 세 가지 속성으로 구성된 JSON 객체여야 합니다."
)


def _safe_content_to_text(content: Any) -> str:
    """OpenAI beta APIs sometimes return string or list content."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts: List[str] = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                texts.append(item.get("text") or "")
            elif isinstance(item, str):
                texts.append(item)
        return "\n".join(texts)
    return str(content)


class ChannelAgent:
    """Wrapper around the OpenAI Agent builder with guardrails."""

    def __init__(self, oa_config: OpenAIConfig, tool_client: ChannelTalkClient):
        oa_config.validate()
        self.config = oa_config
        self.tool_client = tool_client
        self.client = OpenAI(api_key=oa_config.api_key)
        self._agent_id: Optional[str] = None

    @property
    def agent_id(self) -> str:
        if not self._agent_id:
            self._agent_id = self.create_agent()
        return self._agent_id

    def create_agent(self) -> str:
        logger.info("Creating OpenAI Agent for ChannelTalk labeling")
        agent = self.client.beta.v2.agents.create(
            name=self.config.agent_name,
            description=self.config.description,
            model=self.config.model,
            instructions=DEFAULT_INSTRUCTIONS,
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "fetch_user_chat_list",
                        "description": "기간 내 상담 ID 목록을 가져옵니다",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "createdFrom": {"type": "string", "format": "date-time"},
                                "createdTo": {"type": "string", "format": "date-time"},
                            },
                            "required": ["createdFrom", "createdTo"],
                        },
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "fetch_chat_metadata",
                        "description": "특정 상담의 메타 정보를 가져옵니다",
                        "parameters": {
                            "type": "object",
                            "properties": {"userChatId": {"type": "string"}},
                            "required": ["userChatId"],
                        },
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "fetch_chat_messages",
                        "description": "특정 상담의 메시지 목록을 가져옵니다",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "userChatId": {"type": "string"},
                                "limit": {"type": "integer"},
                                "cursor": {"type": "string"},
                            },
                            "required": ["userChatId"],
                        },
                    },
                },
            ],
            guardrails=[
                {
                    "type": "json",
                    "name": "safe_output",
                    "parameters": {
                        "return_schema": {
                            "type": "object",
                            "properties": {
                                "summary": {"type": "string"},
                                "labels": {"type": "array", "items": {"type": "string"}},
                                "emotion": {"type": "string"},
                            },
                            "required": ["summary", "labels"],
                        }
                    },
                }
            ],
        )
        return agent.id

    def summarize_and_label_dialog(
        self,
        dialog_text: str,
        agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Call the agent to summarize and label a single dialog."""
        if not dialog_text:
            raise ValueError("dialog_text is empty")

        active_agent_id = agent_id or self.agent_id
        logger.debug("Calling agent %s for summarization", active_agent_id)
        response = self.client.beta.v2.chat.completions.create(
            agent_id=active_agent_id,
            messages=[{"role": "user", "content": dialog_text}],
        )
        message = response.choices[0].message
        content_text = _safe_content_to_text(message.content)
        try:
            parsed = json.loads(content_text)
        except json.JSONDecodeError:
            logger.warning("Agent responded with non-JSON; wrapping as fallback")
            parsed = {"summary": content_text, "labels": [], "emotion": ""}
        return parsed
