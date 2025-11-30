"""Utility helpers for demo conversations and raw payload handling."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from src.models.conversation import Conversation, Message


def load_conversations(raw_dir: Path) -> List[Conversation]:
    """Load demo conversations from user_chats/messages files under raw_dir."""

    user_chats_path = raw_dir / "user_chats.json"
    if not user_chats_path.exists():
        raise FileNotFoundError(f"user_chats.json을 찾을 수 없습니다: {user_chats_path}")

    payload = json.loads(user_chats_path.read_text(encoding="utf-8"))
    user_chats = payload.get("userChats") or []

    messages_map: Dict[str, List[Message]] = {}
    for user_chat in user_chats:
        conv_id = str(user_chat.get("id"))
        msg_path = raw_dir / f"messages_{conv_id}.json"
        if msg_path.exists():
            messages_payload = json.loads(msg_path.read_text(encoding="utf-8"))
            messages_map[conv_id] = _build_messages(conv_id, messages_payload)
        else:
            messages_map[conv_id] = []

    conversations: List[Conversation] = []
    for user_chat in user_chats:
        conversations.append(_build_conversation(user_chat, messages_map))
    return conversations


def save_raw_payload(raw_dir: Path, user_chats_payload: dict, messages_payloads: Dict[str, dict]) -> None:
    """Persist user chat payload + per-conversation message payloads."""

    raw_dir.mkdir(parents=True, exist_ok=True)
    user_chats_path = raw_dir / "user_chats.json"
    user_chats_path.write_text(json.dumps(user_chats_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    for conv_id, payload in messages_payloads.items():
        msg_path = raw_dir / f"messages_{conv_id}.json"
        msg_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def save_domain_snapshot(conversations: List[Conversation], dest_dir: Path) -> tuple[Path, Path]:
    """Save simplified domain snapshot and return (domain_path, ids_path)."""

    dest_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.utcnow().isoformat(),
        "inquiries": [
            {
                "id": convo.id,
                "channel_id": convo.channel_id,
                "created_at": convo.created_at.isoformat(),
                "closed_at": convo.closed_at.isoformat() if convo.closed_at else None,
                "messages": [msg.text for msg in convo.messages],
            }
            for convo in conversations
        ],
    }
    output_path = dest_dir / "demo_inquiries.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    ids_path = dest_dir / "new_inquiry_ids.json"
    ids_path.write_text(
        json.dumps([convo.id for convo in conversations], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path, ids_path


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
