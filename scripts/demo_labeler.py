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

from src.demo.conversations import load_conversations
from src.models.conversation import Conversation
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


def main() -> None:
    library_path = SAMPLES_DIR / "demo_library.json"
    if not library_path.exists():
        raise SystemExit("demo_library.json이 없습니다. 먼저 `make demo-samples`를 실행하세요.")

    if "OPENAI_API_KEY" not in os.environ:
        raise SystemExit("OPENAI_API_KEY가 설정되어 있지 않습니다.")

    library = SampleLibrary.from_dict(json.loads(library_path.read_text(encoding="utf-8")))
    raw_dir = Path(os.environ.get("DEMO_RAW_DIR", RAW_DEMO_DIR))
    conversations = load_conversations(raw_dir)

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
        "errors": result.errors,
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"라벨링 완료: {len(result.records)}건 → {output_path}")
    for record in result.records:
        print(f"- {record.conversation_id}: {record.result.label_primary} (confidence={record.result.confidence})")
    if result.failed:
        print("실패 ID:", ", ".join(result.failed))
        for convo_id in result.failed:
            detail = result.errors.get(convo_id, "(no error message)")
            print(f"  - {convo_id}: {detail}")


if __name__ == "__main__":
    main()
