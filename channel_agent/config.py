import os
from dataclasses import dataclass
from typing import Optional, Tuple

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
    disable_local_mask: bool = False
    # Few-shot 샘플 검색/포함 옵션
    use_sample_index: bool = False
    sample_top_k: int = 3
    sample_use_mock_embeddings: bool = True
    sample_embed_model: str = "text-embedding-3-small"
    # Off-topic / abuse filtering
    service_keywords: Tuple[str, ...] = (
        "배송",
        "환불",
        "반품",
        "결제",
        "강사",
        "코스",
        "강의",
        "도서",
        "기능",
        "버그",
        "에러",
        "문의",
        "계정",
        "로그인",
        "샘플",
        "영상",
        "수업",
        "강좌",
        "교재",
        "환급",
        "지연",
        "오류",
        "장애",
        "접속",
        "리뷰",
        "품질",
    )
    abuse_threshold: int = 2  # 욕설 카운트가 이 값 이상이고 서비스 키워드가 없으면 드롭
    skipped_output_file: str = "skipped_chats.csv"
