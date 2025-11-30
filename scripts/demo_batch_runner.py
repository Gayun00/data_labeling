"""Demo batch runner: build inquiries and trigger labeling automatically."""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import demo_labeler  # type: ignore
from src.models.conversation import Conversation

DATA_DIR = ROOT / "data"
DOMAIN_DIR = DATA_DIR / "domain"
RAW_DEMO_DIR = DATA_DIR / "raw" / "demo"


def simplify(conversation: Conversation) -> Dict[str, Any]:
    data = asdict(conversation)
    return {
        "id": data["id"],
        "channel_id": data["channel_id"],
        "created_at": conversation.created_at.isoformat(),
        "closed_at": conversation.closed_at.isoformat() if conversation.closed_at else None,
        "messages": [msg.text for msg in conversation.messages],
    }


def save_domain(conversations: List[Conversation]) -> Path:
    DOMAIN_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "inquiries": [simplify(conv) for conv in conversations],
        "generated_from": str(RAW_DEMO_DIR),
    }
    output_path = DOMAIN_DIR / "demo_inquiries.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    ids = [conv.id for conv in conversations]
    ids_path = DOMAIN_DIR / "new_inquiry_ids.json"
    ids_path.write_text(json.dumps(ids, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"도메인 저장: {output_path} (ids={len(ids)})")
    print(f"신규 ID 기록: {ids_path}")
    return ids_path


def main() -> None:
    conversations = demo_labeler.load_conversations()
    if not conversations:
        raise SystemExit("처리할 대화가 없습니다.")
    save_domain(conversations)
    print("라벨러 자동 실행...")
    demo_labeler.main()


if __name__ == "__main__":
    main()
