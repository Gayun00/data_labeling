"""Demo batch runner: build inquiries and trigger labeling automatically."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import demo_labeler  # type: ignore
from src.demo.conversations import load_conversations, save_domain_snapshot

DATA_DIR = ROOT / "data"
DOMAIN_DIR = DATA_DIR / "domain"
RAW_DEMO_DIR = DATA_DIR / "raw" / "demo"


def main() -> None:
    raw_dir = Path(os.environ.get("DEMO_RAW_DIR", RAW_DEMO_DIR))
    conversations = load_conversations(raw_dir)
    if not conversations:
        raise SystemExit("처리할 대화가 없습니다.")
    domain_path, ids_path = save_domain_snapshot(conversations, DOMAIN_DIR)
    print(f"도메인 스냅샷: {domain_path}, 신규 ID: {ids_path}")
    print("라벨러 자동 실행...")
    os.environ.setdefault("DEMO_RAW_DIR", str(raw_dir))
    demo_labeler.main()


if __name__ == "__main__":
    main()
