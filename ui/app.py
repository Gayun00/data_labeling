from __future__ import annotations

import io
import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
import streamlit as st
from streamlit.runtime.uploaded_file_manager import UploadedFile

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.adapters.channel_talk_csv import ChannelTalkCSVAdapter
from src.embeddings import TfidfEmbedder
from src.models.conversation import Conversation
from src.models.sample import SampleLibrary, SampleRecord
from src.samples.manager import SampleManager
from src.vector_store import VectorStore

DATA_DIR = Path("data")
SAMPLE_DIR = DATA_DIR / "samples"
SAMPLE_UPLOAD_DIR = SAMPLE_DIR / "uploads"
SAMPLE_LIBRARY_PATH = SAMPLE_DIR / "library.json"
RAW_DIR = DATA_DIR / "raw"
NORMALIZED_DIR = DATA_DIR / "normalized"

RAW_ALLOWED_EXTENSIONS = {".xlsx", ".xls", ".csv"}


def main() -> None:
    st.set_page_config(page_title="Review Labeling MVP", layout="wide")

    st.title("📮 Review Labeling MVP")

    init_state()

    tab1, tab2 = st.tabs(["샘플 관리", "원본 데이터 정규화"])

    with tab1:
        render_sample_intro()
        render_sample_section()
        render_sample_overview()

    with tab2:
        render_raw_data_section()


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
    st.session_state.setdefault("raw_data_info", None)


def render_sample_intro() -> None:
    st.markdown(
        "라벨된 샘플 CSV를 업로드해 샘플 라이브러리를 구축하세요. "
        "업로드된 샘플은 임베딩 후 벡터 스토어에 저장되어 이후 신규 문의 분류에 활용됩니다."
    )


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
            st.rerun()

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


def render_raw_data_section() -> None:
    st.subheader("채널톡 원본 데이터 업로드")
    st.markdown("엑셀 또는 CSV 원본을 업로드하면 시트별 구조를 분석하고 정규화된 데이터를 제공합니다.")

    info = st.session_state.get("raw_data_info")

    if info:
        uploaded_at: datetime = info["uploaded_at"]
        saved_path = info.get("saved_path")
        st.success(
            f"최근 업로드 파일: {info['original_name']} · 업로드 시각 {uploaded_at.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        if saved_path and Path(saved_path).exists():
            download_data = Path(saved_path).read_bytes()
            st.download_button(
                "원본 파일 다운로드",
                data=download_data,
                file_name=Path(saved_path).name,
                mime="application/octet-stream",
                key="download_raw_file",
            )
        normalized_records = info.get("normalized_records") or []
        normalized_path = info.get("normalized_path")

        cols = st.columns(2)
        with cols[0]:
            if saved_path and Path(saved_path).exists():
                download_data = Path(saved_path).read_bytes()
                st.download_button(
                    "원본 파일 다운로드",
                    data=download_data,
                    file_name=Path(saved_path).name,
                    mime="application/octet-stream",
                    key="download_raw_file",
                )
        with cols[1]:
            if normalized_records:
                json_bytes = json.dumps(normalized_records, ensure_ascii=False, indent=2).encode("utf-8")
                st.download_button(
                    "정규화 JSON 다운로드",
                    data=json_bytes,
                    file_name="normalized_conversations.json",
                    mime="application/json",
                )
            if normalized_path and Path(normalized_path).exists():
                csv_bytes = Path(normalized_path).read_bytes()
                st.download_button(
                    "정규화 CSV 다운로드",
                    data=csv_bytes,
                    file_name=Path(normalized_path).name,
                    mime="text/csv",
                )

        if st.button("원본 데이터 초기화", key="raw_reset"):
            clear_raw_data()
            st.rerun()

        summaries = info.get("sheet_summaries", [])
        for summary in summaries:
            with st.expander(f"시트: {summary['name']} ({summary['rows']}행, {summary['cols']}열)"):
                st.dataframe(summary["preview"], use_container_width=True)

    uploaded_file = st.file_uploader(
        "채널톡 Export 파일 업로드",
        type=["xlsx", "xls", "csv"],
        key="raw_upload",
    )
    save_to_disk = st.checkbox("원본 파일 보관", value=True, key="raw_save")

    if uploaded_file and st.button("원본 데이터 처리", key="process_raw"):
        try:
            info = process_raw_upload(uploaded_file, save_to_disk=save_to_disk)
        except Exception as exc:  # pragma: no cover - surfaced to UI
            st.error(f"원본 데이터 처리 중 오류가 발생했습니다: {exc}")
        else:
            st.session_state["raw_data_info"] = info
            st.success("원본 데이터 처리 및 요약이 완료되었습니다.")
            st.rerun()


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


def process_raw_upload(uploaded_file: UploadedFile, save_to_disk: bool) -> Dict[str, Any]:
    extension = Path(uploaded_file.name).suffix.lower()
    if extension not in RAW_ALLOWED_EXTENSIONS:
        raise ValueError(f"지원하지 않는 파일 확장자입니다: {extension}")

    file_bytes = uploaded_file.getvalue()
    saved_path: Optional[Path] = None
    if save_to_disk:
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        saved_path = RAW_DIR / f"raw_{timestamp}{extension}"
        saved_path.write_bytes(file_bytes)

    dataframes = read_raw_file(file_bytes, extension)

    sheet_summaries = []
    for name, df in dataframes.items():
        sheet_summaries.append(
            {
                "name": name,
                "rows": int(df.shape[0]),
                "cols": int(df.shape[1]),
                "columns": [str(col) for col in df.columns],
                "preview": df.head(5),
            }
        )

    normalized_records, normalized_path = normalize_conversations(dataframes)

    return {
        "original_name": uploaded_file.name,
        "extension": extension,
        "uploaded_at": datetime.utcnow(),
        "saved_path": str(saved_path) if saved_path else None,
        "sheet_summaries": sheet_summaries,
        "dataframes": dataframes,
        "normalized_records": normalized_records,
        "normalized_path": normalized_path,
    }


def read_raw_file(file_bytes: bytes, extension: str) -> Dict[str, pd.DataFrame]:
    buffer = io.BytesIO(file_bytes)
    if extension in {".xlsx", ".xls"}:
        return pd.read_excel(buffer, sheet_name=None)
    buffer.seek(0)
    return {"csv": pd.read_csv(buffer)}


def clear_library() -> None:
    if SAMPLE_LIBRARY_PATH.exists():
        SAMPLE_LIBRARY_PATH.unlink()
    st.session_state["sample_library"] = None
    st.session_state["sample_ingestion_result"] = None
    st.session_state["vector_store"] = VectorStore()
    st.session_state["vector_store_rehydrated"] = True


def clear_raw_data() -> None:
    info = st.session_state.get("raw_data_info")
    if info:
        saved_path = info.get("saved_path")
        if saved_path:
            path = Path(saved_path)
            try:
                if path.exists() and RAW_DIR.resolve() in path.resolve().parents:
                    path.unlink()
            except OSError:
                pass
    st.session_state["raw_data_info"] = None


def normalize_conversations(dataframes: Dict[str, pd.DataFrame]) -> tuple[list[Dict[str, Any]], Optional[str]]:
    adapter = ChannelTalkCSVAdapter(dataframes)
    conversations = list(adapter.conversations())

    records: list[Dict[str, Any]] = []
    for convo in conversations:
        records.append(
            {
                "conversation_id": convo.id,
                "channel_id": convo.channel_id,
                "created_at": convo.created_at.isoformat(),
                "closed_at": convo.closed_at.isoformat() if convo.closed_at else None,
                "user_id": convo.participants.user.id if convo.participants.user else None,
                "user_email": convo.participants.user.email if convo.participants.user else None,
                "manager_ids": ",".join(manager.id for manager in convo.participants.managers),
                "message_count": len(convo.messages),
                "transcript": "\n".join(
                    f"[{message.created_at.isoformat()}] {message.sender_type}: {message.text}" for message in convo.messages
                ),
                "meta": json.dumps(convo.meta, ensure_ascii=False),
            }
        )

    if not records:
        return records, None

    NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    csv_path = NORMALIZED_DIR / f"conversations_{timestamp}.csv"
    df = pd.DataFrame(records)
    df.to_csv(csv_path, index=False)
    return records, str(csv_path)


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
