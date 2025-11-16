import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv


load_dotenv()


@dataclass
class ChannelTalkConfig:
    """Configuration for ChannelTalk API access."""

    access_key: str = os.getenv("CHANNELTALK_ACCESS_KEY", "")
    access_secret: str = os.getenv("CHANNELTALK_ACCESS_SECRET", "")
    base_url: str = os.getenv("CHANNELTALK_BASE_URL", "https://open.channel.io")

    def validate(self) -> None:
        if not self.access_key or not self.access_secret:
            raise ValueError(
                "CHANNELTALK_ACCESS_KEY and CHANNELTALK_ACCESS_SECRET must be set"
            )


@dataclass
class OpenAIConfig:
    """Configuration for the OpenAI Agent."""

    api_key: str = os.getenv("OPENAI_API_KEY", "")
    model: str = os.getenv("OPENAI_MODEL", "gpt-4-1106-preview")
    agent_name: str = os.getenv("OPENAI_AGENT_NAME", "ChannelTalkLabeler")
    description: str = os.getenv(
        "OPENAI_AGENT_DESCRIPTION", "채널톡 상담 데이터를 요약하고 라벨링합니다."
    )

    def validate(self) -> None:
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY must be set")


@dataclass
class PipelineConfig:
    """Runtime knobs for the labeling pipeline."""

    message_page_size: int = 100
    output_dir: str = os.getenv("CHANNEL_OUTPUT_DIR", "data/channel/results")
    output_file: str = "labeled_chats.csv"
    agent_instructions: Optional[str] = None

