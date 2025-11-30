"""Ingest demo samples from CSV and embed them."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.embeddings.tfidf import TfidfEmbedder
from src.samples.manager import SampleManager
from src.vector_store import VectorStore

DATA_DIR = ROOT / "data" / "samples"


def main() -> None:
    csv_path = DATA_DIR / "demo_samples.csv"
    library_path = DATA_DIR / "demo_library.json"
    vectors_path = DATA_DIR / "demo_vectors.json"

    embedder = TfidfEmbedder(max_features=32)
    vector_store = VectorStore()
    manager = SampleManager(embedder=embedder, vector_store=vector_store)

    result = manager.ingest_from_csv(csv_path, origin="demo", auto_embed=True)
    print(f"loaded {len(result.library)} samples; embedded={result.embedded_count}; skipped={result.skipped_count}")
    if result.errors:
        print("errors:")
        for error in result.errors:
            print("  -", error)

    library_path.write_text(json.dumps(result.library.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    vectors = [
        {
            "sample_id": entry.sample_id,
            "vector_id": entry.vector_id,
            "embedding": entry.embedding,
        }
        for entry in vector_store.list_sample_vectors()
    ]
    vectors_path.write_text(json.dumps(vectors, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved library -> {library_path}")
    print(f"saved vectors -> {vectors_path}")


if __name__ == "__main__":
    main()
