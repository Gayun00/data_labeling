from pathlib import Path
from typing import List, Sequence

import pandas as pd

from src.models.sample import SampleRecord
from src.samples.manager import EmbeddingBackend, SampleManager, SampleVectorStore
from src.vector_store import VectorStore


class DummyEmbedder(EmbeddingBackend):
    def embed(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        return [[float(len(text))] for text in texts]


class DummyVectorStore(VectorStore, SampleVectorStore):
    pass


def write_sample_csv(path: Path) -> None:
    df = pd.DataFrame(
        [
            {
                "sample_id": "sample-1",
                "label_primary": "complaint",
                "label_secondary": "bug",
                "summary": "앱이 자꾸 종료돼서 불편하다.",
                "raw_text": "어제부터 앱이 실행 1분 만에 꺼집니다.",
                "source_conversation_id": "chat-101",
                "extra": "mobile",
            },
            {
                "label_primary": "inquiry",
                "summary": "결제 영수증 발급 문의.",
            },
        ]
    )
    df.to_csv(path, index=False)


def test_ingest_from_csv(tmp_path: Path) -> None:
    csv_path = tmp_path / "samples.csv"
    write_sample_csv(csv_path)

    manager = SampleManager(embedder=DummyEmbedder(), vector_store=DummyVectorStore())
    result = manager.ingest_from_csv(csv_path)

    assert result.skipped_count == 0
    assert result.embedded_count == 2
    assert not result.errors

    library_records = list(result.library)
    assert len(library_records) == 2

    first = result.library.get("sample-1")
    assert first is not None
    assert first.label_primary == "complaint"
    assert first.label_secondary == ["bug"]
    assert first.meta.get("extra") == "mobile"

    second = library_records[1]
    assert second.sample_id != ""
    assert second.label_primary == "inquiry"
