from __future__ import annotations

import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st
from streamlit.runtime.uploaded_file_manager import UploadedFile

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.embeddings import TfidfEmbedder
from src.models.sample import SampleLibrary, SampleRecord
from src.samples.manager import SampleManager
from src.vector_store import VectorStore

DATA_DIR = Path("data")
SAMPLE_DIR = DATA_DIR / "samples"
SAMPLE_UPLOAD_DIR = SAMPLE_DIR / "uploads"
SAMPLE_LIBRARY_PATH = SAMPLE_DIR / "library.json"


def main() -> None:
    st.set_page_config(page_title="Review Labeling MVP", layout="wide")

    st.title("📮 Review Labeling MVP")
    st.markdown(
        "라벨된 샘플 CSV를 업로드해 샘플 라이브러리를 구축하세요. "
        "업로드된 샘플은 임베딩 후 벡터 스토어에 저장되어 이후 신규 문의 분류에 활용됩니다."
    )

    init_state()
    render_sample_section()
    render_sample_overview()


def init_state() -> None:
    if "vector_store" not in st.session_state:
        st.session_state["vector_store"] = VectorStore()
    st.session_state.setdefault("vector_store_rehydrated", False)

    if "sample_library" not in st.session_state:
        library = load_library_from_disk()
        st.session_state["sample_library"] = library
        rebuild_vector_store(library)
    elif not st.session_state["vector_store_rehydrated"]:
        rebuild_vector_store(st.session_state.get("sample_library"))

    st.session_state.setdefault("sample_ingestion_result", None)


def render_sample_section() -> None:
    st.subheader("1️⃣ 샘플 CSV 업로드")
    st.caption("필수 컬럼: `label_primary`, `summary` (optional: `sample_id`, `label_secondary`, `raw_text`, etc.)")

    current_library: Optional[SampleLibrary] = st.session_state.get("sample_library")
    if current_library and len(current_library):
        st.info(
            f"현재 저장된 샘플 {len(current_library)}건 · "
            f"업데이트 시각 {current_library.created_at.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        if st.button("샘플 라이브러리 비우기", type="secondary"):
            clear_library()
            st.experimental_rerun()

    uploaded_file = st.file_uploader("샘플 CSV 선택", type=["csv"], key="sample_upload")
    auto_embed = st.checkbox("업로드와 동시에 임베딩 실행", value=True)

    col1, col2 = st.columns([1, 1])
    with col1:
        save_to_disk = st.checkbox("CSV 파일 보관", value=True)
    with col2:
        origin_label = st.text_input("출처 라벨", value="ui_upload", max_chars=40)

    if uploaded_file and st.button("샘플 등록", type="primary"):
        path = save_uploaded_file(uploaded_file) if save_to_disk else write_temp_file(uploaded_file)
        try:
            embedder = TfidfEmbedder() if auto_embed else None
            manager = SampleManager(
                embedder=embedder,
                vector_store=st.session_state["vector_store"],
            )
            result = manager.ingest_from_csv(path, origin=origin_label, auto_embed=auto_embed)
        except Exception as exc:  # broad to show error in UI
            st.error(f"샘플 업로드 중 오류가 발생했습니다: {exc}")
            return

        existing_library: Optional[SampleLibrary] = st.session_state.get("sample_library")
        merged_library = result.library
        if existing_library:
            merged_library = existing_library.merge(result.library)

        persist_library(merged_library)
        rebuild_vector_store(merged_library)

        st.session_state["sample_library"] = merged_library
        st.session_state["sample_ingestion_result"] = result

        st.success(
            f"샘플 {len(merged_library)}건 라이브러리 저장 완료 · 임베딩 {result.embedded_count}건 · "
            f"스킵 {result.skipped_count}건"
        )
        if result.errors:
            with st.expander("처리 중 오류 상세", expanded=False):
                for error in result.errors:
                    st.write(f"- {error}")


def render_sample_overview() -> None:
    library: Optional[SampleLibrary] = st.session_state.get("sample_library")
    result = st.session_state.get("sample_ingestion_result")

    st.subheader("2️⃣ 샘플 라이브러리 현황")
    if not library:
        st.info("아직 업로드된 샘플이 없습니다. CSV를 업로드해 라이브러리를 초기화하세요.")
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("샘플 수", len(library))
    with col2:
        st.metric("출처", library.origin)
    with col3:
        st.metric("업데이트 시각", library.created_at.strftime("%Y-%m-%d %H:%M:%S"))

    vector_store: VectorStore = st.session_state["vector_store"]
    embedding_count = sum(1 for _ in vector_store.list_sample_vectors())
    st.caption(f"임베딩 저장 수: {embedding_count}")

    df = library_to_dataframe(library)
    st.dataframe(df, use_container_width=True, hide_index=True)

    if result and result.errors:
        st.warning(f"처리 중 오류 {len(result.errors)}건이 발생했습니다. 상세 내역을 확인하세요.")


def save_uploaded_file(uploaded_file: UploadedFile) -> Path:
    SAMPLE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    path = SAMPLE_UPLOAD_DIR / f"samples_{timestamp}.csv"
    path.write_bytes(uploaded_file.getbuffer())
    return path


def write_temp_file(uploaded_file: UploadedFile) -> Path:
    tmp_dir = DATA_DIR / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    path = tmp_dir / f"upload_{datetime.utcnow().timestamp()}.csv"
    path.write_bytes(uploaded_file.getbuffer())
    return path


def load_library_from_disk() -> Optional[SampleLibrary]:
    if not SAMPLE_LIBRARY_PATH.exists():
        return None
    try:
        data = json.loads(SAMPLE_LIBRARY_PATH.read_text(encoding="utf-8"))
        return SampleLibrary.from_dict(data)
    except Exception as exc:
        st.error(f"샘플 라이브러리를 불러오는 중 오류가 발생했습니다: {exc}")
        return None


def persist_library(library: SampleLibrary) -> None:
    SAMPLE_LIBRARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(library.to_dict(), ensure_ascii=False, indent=2)
    SAMPLE_LIBRARY_PATH.write_text(payload, encoding="utf-8")


def rebuild_vector_store(library: Optional[SampleLibrary]) -> None:
    store = VectorStore()
    if library and len(library):
        embedder = TfidfEmbedder()
        records = list(library)
        embeddings = embedder.embed([record.summary_for_embedding for record in records])
        store.upsert_samples(records, embeddings)
    st.session_state["vector_store"] = store
    st.session_state["vector_store_rehydrated"] = True


def clear_library() -> None:
    if SAMPLE_LIBRARY_PATH.exists():
        SAMPLE_LIBRARY_PATH.unlink()
    st.session_state["sample_library"] = None
    st.session_state["sample_ingestion_result"] = None
    st.session_state["vector_store"] = VectorStore()
    st.session_state["vector_store_rehydrated"] = True


def library_to_dataframe(library: SampleLibrary) -> pd.DataFrame:
    rows = []
    for record in library:
        rows.append(sample_record_to_row(record))
    return pd.DataFrame(rows)


def sample_record_to_row(record: SampleRecord) -> dict:
    data = asdict(record)
    meta = data.pop("meta", {}) or {}
    data["meta"] = json.dumps(meta, ensure_ascii=False) if meta else ""
    data["created_at"] = record.created_at.strftime("%Y-%m-%d %H:%M:%S") if record.created_at else ""
    data["label_secondary"] = ", ".join(record.label_secondary)
    data["summary_for_embedding"] = record.summary_for_embedding[:120] + (
        "..." if len(record.summary_for_embedding) > 120 else ""
    )
    return data


if __name__ == "__main__":
    main()
