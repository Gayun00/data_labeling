"""Run a miniature labeling pipeline using demo data and OpenAI."""
from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

from src.models.conversation import Conversation, Message
from src.models.label import LabelRecord
from src.models.sample import SampleLibrary
from src.pipeline.labeling import LLMService, LabelingPipeline
from src.retrieval import SimilarityRetriever

DATA_DIR = ROOT / "data"
RAW_DEMO_DIR = DATA_DIR / "raw" / "demo"
SAMPLES_DIR = DATA_DIR / "samples"
RESULTS_DIR = DATA_DIR / "results"


def to_serializable(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, list):
        return [to_serializable(item) for item in obj]
    if isinstance(obj, dict):
        return {key: to_serializable(value) for key, value in obj.items()}
    return obj


def load_conversations() -> List[Conversation]:
    payload = _read_json(RAW_DEMO_DIR / "user_chats.json")
    user_chats = payload.get("userChats") or []
    messages_map: Dict[str, List[Message]] = {}

    for user_chat in user_chats:
        conv_id = str(user_chat.get("id"))
        messages_path = RAW_DEMO_DIR / f"messages_{conv_id}.json"
        if messages_path.exists():
            messages_payload = _read_json(messages_path)
            messages_map[conv_id] = _build_messages(conv_id, messages_payload)
        else:
            messages_map[conv_id] = []

    conversations: List[Conversation] = []
    for user_chat in user_chats:
        conversations.append(_build_conversation(user_chat, messages_map))
    return conversations


def _build_messages(conv_id: str, payload: dict) -> List[Message]:
    messages: List[Message] = []
    for msg in payload.get("messages", []):
        created_at = datetime.fromtimestamp(msg.get("createdAt", 0))
        messages.append(
            Message(
                id=str(msg.get("id")),
                conversation_id=conv_id,
                sender_type=str(msg.get("personType")),
                sender_id=msg.get("personId"),
                created_at=created_at,
                text=msg.get("plainText") or "",
            )
        )
    return sorted(messages, key=lambda m: m.created_at)


def _build_conversation(user_chat: dict, messages_map: Dict[str, List[Message]]) -> Conversation:
    conv_id = str(user_chat.get("id"))
    created_at = datetime.fromtimestamp(user_chat.get("createdAt", 0))
    closed_at_raw = user_chat.get("closedAt")
    closed_at = datetime.fromtimestamp(closed_at_raw) if closed_at_raw else None

    return Conversation(
        id=conv_id,
        channel_id=user_chat.get("channelId"),
        created_at=created_at,
        closed_at=closed_at,
        participants=None,
        messages=messages_map.get(conv_id, []),
        meta={},
    )


def _read_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    library_path = SAMPLES_DIR / "demo_library.json"
    if not library_path.exists():
        raise SystemExit("demo_library.json이 없습니다. 먼저 `make demo-samples`를 실행하세요.")

    if "OPENAI_API_KEY" not in os.environ:
        raise SystemExit("OPENAI_API_KEY가 설정되어 있지 않습니다.")

    library = SampleLibrary.from_dict(json.loads(library_path.read_text(encoding="utf-8")))
    conversations = load_conversations()

    retriever = SimilarityRetriever(top_k=3)
    model_name = os.environ.get("LABELER_MODEL", "gpt-4o-mini")
    temperature = float(os.environ.get("LABELER_TEMPERATURE", "0.1"))
    llm_service = LLMService(model=model_name, temperature=temperature)
    pipeline = LabelingPipeline(retriever=retriever, llm_service=llm_service)
    schema = sorted({record.label_primary for record in library})

    result = pipeline.run(conversations, library, label_schema=schema)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = RESULTS_DIR / "demo_labels.json"

    payload = {
        "records": [to_serializable(asdict(record)) for record in result.records],
        "failed": result.failed,
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"라벨링 완료: {len(result.records)}건 → {output_path}")
    for record in result.records:
        print(f"- {record.conversation_id}: {record.result.label_primary} (confidence={record.result.confidence})")
    if result.failed:
        print("실패 ID:", ", ".join(result.failed))


if __name__ == "__main__":
    main()
