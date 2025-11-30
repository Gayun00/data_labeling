"""Quick demo: raw ChannelTalk JSON -> Conversation dataclasses."""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.models.conversation import Conversation, Message

DATA_DIR = Path("data/raw/demo")


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def to_serializable(data: Any) -> Any:
    if isinstance(data, datetime):
        return data.isoformat()
    if isinstance(data, list):
        return [to_serializable(item) for item in data]
    if isinstance(data, dict):
        return {key: to_serializable(value) for key, value in data.items()}
    return data


def build_messages(user_chat_id: str, payload: dict) -> List[Message]:
    messages = payload.get("messages") or []
    results: List[Message] = []
    for msg in messages:
        created_at = datetime.fromtimestamp(msg.get("createdAt", 0))
        results.append(
            Message(
                id=str(msg.get("id")),
                conversation_id=user_chat_id,
                sender_type=str(msg.get("personType")),
                sender_id=msg.get("personId"),
                created_at=created_at,
                text=msg.get("plainText") or "",
            )
        )
    # sort chronologically
    return sorted(results, key=lambda message: message.created_at)


def build_conversation(user_chat: dict, messages_map: Dict[str, List[Message]]) -> Conversation:
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
def simplify_conversation(conversation: Conversation) -> Dict[str, Any]:
    base: Dict[str, Any] = {
        "id": conversation.id,
        "channel_id": conversation.channel_id,
        "created_at": conversation.created_at,
    }
    if conversation.closed_at:
        base["closed_at"] = conversation.closed_at

    base["messages"] = [msg.text for msg in conversation.messages]
    return base


def main() -> None:
    user_chats_payload = load_json(DATA_DIR / "user_chats.json")
    user_chats = user_chats_payload.get("userChats") or []

    messages_map: Dict[str, List[Message]] = {}
    for conversation in user_chats:
        conv_id = str(conversation.get("id"))
        messages_path = DATA_DIR / f"messages_{conv_id}.json"
        if messages_path.exists():
            messages_payload = load_json(messages_path)
            messages_map[conv_id] = build_messages(conv_id, messages_payload)
        else:
            messages_map[conv_id] = []

    conversations: List[Conversation] = []
    for conversation in user_chats:
        conv = build_conversation(conversation, messages_map)
        conversations.append(conv)
        print("===== Conversation", conv.id)
        simplified = simplify_conversation(conv)
        print(json.dumps(to_serializable(simplified), ensure_ascii=False, indent=2))

    print(f"총 {len(conversations)}건 변환 완료")


if __name__ == "__main__":
    main()
