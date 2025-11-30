from __future__ import annotations

import io
import json
import os
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st
from streamlit.runtime.uploaded_file_manager import UploadedFile
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
load_dotenv(ROOT_DIR / ".env")

from config import get_settings
from src.adapters.channel_talk_csv import ChannelTalkCSVAdapter
from src.adapters.mock_channel_api import MockChannelTalkAPI
from src.embeddings import TfidfEmbedder
from src.demo.conversations import load_conversations, save_domain_snapshot, save_raw_payload
from src.models.conversation import Conversation
from src.models.label import LabelRecord
from src.models.sample import SampleLibrary, SampleRecord
from src.pipeline import LabelingPipeline
from src.pipeline.labeling import LLMService
from src.retrieval import SimilarityRetriever
from src.samples.manager import SampleManager
from src.vector_store import VectorStore

DATA_DIR = Path("data")
SAMPLE_DIR = DATA_DIR / "samples"
SAMPLE_UPLOAD_DIR = SAMPLE_DIR / "uploads"
SAMPLE_LIBRARY_PATH = SAMPLE_DIR / "library.json"
RAW_DIR = DATA_DIR / "raw"
NORMALIZED_DIR = DATA_DIR / "normalized"
MOCK_BATCH_DIR = DATA_DIR / "mock_batches"

RAW_ALLOWED_EXTENSIONS = {".xlsx", ".xls", ".csv"}


def main() -> None:
    st.set_page_config(page_title="Review Labeling MVP", layout="wide")

    st.title("📮 Review Labeling MVP")

    init_state()

    tab1, tab2, tab3 = st.tabs(["샘플 관리", "원본 데이터 정규화", "Mock API 배치"])

    with tab1:
        render_sample_intro()
        render_sample_section()
        render_sample_overview()

    with tab2:
        render_raw_data_section()

    with tab3:
        render_mock_batch_tab()


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
    st.session_state.setdefault("labeling_result", None)
    st.session_state.setdefault("mock_batch_info", None)
    st.session_state.setdefault("mock_batch_df", None)
    st.session_state.setdefault("mock_batch_conversations", None)


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


def render_labeling_section(info: Dict[str, Any]) -> None:
    st.subheader("정규화 데이터 라벨링")

    conversations: List[Conversation] = info.get("conversations") or []
    library: Optional[SampleLibrary] = st.session_state.get("sample_library")

    if not conversations:
        st.info("정규화된 대화가 없습니다. 원본 데이터를 먼저 업로드하세요.")
        return

    if not library or len(library) == 0:
        st.warning("샘플 라이브러리가 필요합니다. 먼저 샘플 CSV를 업로드하세요.")
        return

    settings = get_settings()
    label_schema = [item.id for item in settings.labels.schema]

    use_llm = st.checkbox("LLM으로 라벨 분류 실행", value=False, key="use_llm")

    if st.button("정규화된 대화 라벨링 실행", type="primary", key="run_labeling"):
        retriever = SimilarityRetriever(
            top_k=settings.retrieval.sample_top_k,
            min_similarity=settings.retrieval.min_similarity,
        )

        llm_service = None
        if use_llm:
            try:
                llm_service = LLMService(model=settings.llm.model_name, temperature=settings.llm.temperature)
            except Exception as exc:
                st.error(f"LLM 서비스를 초기화할 수 없습니다: {exc}")
                return

        pipeline = LabelingPipeline(retriever, llm_service=llm_service)
        result = pipeline.run(conversations, library, label_schema)
        st.session_state["labeling_result"] = result
        df = label_records_to_dataframe(result.records)
        st.session_state["labeling_result_df"] = df

        st.success(f"총 {len(result.records)}건 라벨링 완료")
        if result.failed:
            st.warning(f"LLM 호출 실패 {len(result.failed)}건: {', '.join(result.failed)}")
            for convo_id in result.failed:
                st.text(f"- {convo_id}: {result.errors.get(convo_id, '(error message unavailable)')}")

    render_labeling_overview()


def render_labeling_overview() -> None:
    result = st.session_state.get("labeling_result")
    df: Optional[pd.DataFrame] = st.session_state.get("labeling_result_df")

    if not result or df is None:
        return

    st.subheader("라벨링 결과")
    st.dataframe(df, use_container_width=True, hide_index=True)

    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "라벨 결과 CSV 다운로드",
        data=csv_bytes,
        file_name="label_results.csv",
        mime="text/csv",
        key="download_labels",
    )

def render_raw_data_section() -> None:
    st.subheader("채널톡 원본 데이터 업로드")
    st.markdown("엑셀 또는 CSV 원본을 업로드하면 시트별 구조를 분석하고 정규화된 데이터를 제공합니다.")

    render_raw_data_form()
    st.divider()
    render_raw_data_overview()


def render_mock_batch_tab() -> None:
    st.subheader("Mock API 배치 데모")
    st.caption("Mock ChannelTalk API에서 데이터를 받아와 도메인 저장 → 라벨링까지 한 번에 실행합니다.")

    library: Optional[SampleLibrary] = st.session_state.get("sample_library")
    if not library or len(library) == 0:
        st.warning("샘플 라이브러리가 필요합니다. 먼저 샘플 CSV를 업로드하세요.")
        return

    count = st.slider("Mock 문의 수", min_value=1, max_value=5, value=3, key="mock_batch_count")
    use_llm = st.checkbox("LLM 호출 사용", value=True, key="mock_batch_use_llm")

    if st.button("Mock API 호출 및 배치 실행", type="primary", key="mock_batch_run"):
        try:
            info = run_mock_batch_pipeline(library, count=count, use_llm=use_llm)
        except Exception as exc:  # pragma: no cover - surfaced to UI
            st.error(f"Mock 배치 실행 중 오류가 발생했습니다: {exc}")
        else:
            st.session_state["mock_batch_info"] = info
            st.session_state["mock_batch_df"] = info.get("labels_df")
            st.session_state["mock_batch_conversations"] = info.get("conversations")
            st.success(f"Mock 배치 완료: {info['count']}건 라벨링")

    render_mock_batch_overview()


def render_mock_batch_overview() -> None:
    info = st.session_state.get("mock_batch_info") or {}
    df: Optional[pd.DataFrame] = st.session_state.get("mock_batch_df")
    conversations = st.session_state.get("mock_batch_conversations") or []

    if not info:
        st.info("아직 Mock 배치를 실행하지 않았습니다.")
        return

    st.success(
        f"최근 실행: {info.get('timestamp', 'N/A')} · 문의 {info.get('count', 0)}건 · 실패 {len(info.get('failed', []))}건"
    )
    st.markdown(
        f"- Raw 디렉터리: `{info['raw_dir']}`\n"
        f"- Domain 스냅샷: `{info['domain_path']}`\n"
        f"- 라벨 JSON: `{info['labels_path']}`"
    )

    labels_path = Path(info["labels_path"])
    if labels_path.exists():
        st.download_button(
            "라벨 JSON 다운로드",
            data=labels_path.read_bytes(),
            file_name=labels_path.name,
            mime="application/json",
            key=f"download_mock_labels_{info.get('timestamp','')}",
        )

    raw_userchats = Path(info["raw_dir"]) / "user_chats.json"
    if raw_userchats.exists():
        raw_payload = json.loads(raw_userchats.read_text(encoding="utf-8"))
        with st.expander("Raw userChats 미리보기"):
            st.json(raw_payload)
        st.download_button(
            "Raw userChats JSON 다운로드",
            data=raw_userchats.read_bytes(),
            file_name=raw_userchats.name,
            mime="application/json",
            key=f"download_mock_raw_{info.get('timestamp','')}",
        )

    ids_path = info.get("ids_path")
    if ids_path and Path(ids_path).exists():
        ids_data = Path(ids_path).read_text(encoding="utf-8")
        with st.expander("신규 inquiry_ids"):
            st.write(json.loads(ids_data))
        st.download_button(
            "new_inquiry_ids.json 다운로드",
            data=ids_data.encode("utf-8"),
            file_name=Path(ids_path).name,
            mime="application/json",
            key=f"download_mock_ids_{info.get('timestamp','')}",
        )

    domain_path = Path(info["domain_path"])
    if domain_path.exists():
        domain_payload = json.loads(domain_path.read_text(encoding="utf-8"))
        with st.expander("도메인 스냅샷 미리보기"):
            st.json(domain_payload)

    if df is not None and not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Mock 배치 라벨 CSV 다운로드",
            data=csv_bytes,
            file_name="mock_batch_labels.csv",
            mime="text/csv",
            key=f"download_mock_csv_{info.get('timestamp','')}",
        )

    failed = info.get("failed") or []
    errors = info.get("errors") or {}
    if failed:
        st.warning(f"라벨링 실패 ID: {', '.join(failed)}")
        for convo_id in failed:
            st.text(f"- {convo_id}: {errors.get(convo_id, '(error message unavailable)')}")

    if conversations:
        st.subheader("라벨링된 대화 상세")
        selected_id = st.selectbox(
            "대화 선택",
            [conv.id for conv in conversations],
            key="mock_batch_convo_selector",
        )
        selected = next((conv for conv in conversations if conv.id == selected_id), None)
        if selected:
            with st.expander(f"대화 {selected.id} 메시지", expanded=True):
                for message in selected.messages:
                    st.markdown(
                        f"**{message.sender_type}** ({message.created_at.strftime('%H:%M:%S')}): {message.text}"
                    )
            matching = None
            if df is not None:
                matching = df[df["conversation_id"] == selected.id]
            if matching is not None and not matching.empty:
                st.table(matching)


def render_raw_data_form() -> None:
    uploaded_file = st.file_uploader(
        "채널톡 Export 파일 업로드",
        type=["xlsx", "xls", "csv"],
        key="raw_upload",
    )
    save_to_disk = st.checkbox("원본 파일 보관", value=True, key="raw_save")

    if uploaded_file and st.button("원본 데이터 정규화 실행", key="process_raw"):
        try:
            info = process_raw_upload(uploaded_file, save_to_disk=save_to_disk)
        except Exception as exc:  # pragma: no cover - surfaced to UI
            st.error(f"원본 데이터 처리 중 오류가 발생했습니다: {exc}")
        else:
            st.session_state["raw_data_info"] = info
            st.success("원본 데이터 처리 및 요약이 완료되었습니다.")
            st.rerun()


def render_raw_data_overview() -> None:
    info = st.session_state.get("raw_data_info")
    if not info:
        st.info("아직 정규화된 데이터가 없습니다. 위에서 원본 파일을 업로드해 주세요.")
        return

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
            key="download_raw_file_header",
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
                key="download_raw_file_main",
            )
    with cols[1]:
        if normalized_records:
            json_bytes = json.dumps(normalized_records, ensure_ascii=False, indent=2).encode("utf-8")
            st.download_button(
                "정규화 JSON 다운로드",
                data=json_bytes,
                file_name="normalized_conversations.json",
                mime="application/json",
                key="download_normalized_json",
            )
        if normalized_path and Path(normalized_path).exists():
            csv_bytes = Path(normalized_path).read_bytes()
            st.download_button(
                "정규화 CSV 다운로드",
                data=csv_bytes,
                file_name=Path(normalized_path).name,
                mime="text/csv",
                key="download_normalized_csv",
            )

    if st.button("원본 데이터 초기화", key="raw_reset"):
        clear_raw_data()
        st.rerun()

    summaries = info.get("sheet_summaries", [])
    for summary in summaries:
        with st.expander(f"시트: {summary['name']} ({summary['rows']}행, {summary['cols']}열)"):
            st.dataframe(summary["preview"], use_container_width=True)

    st.divider()
    render_labeling_section(info)


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
    print(f"[process_raw_upload] 시작 - 파일명: {uploaded_file.name}, 크기: {len(uploaded_file.getvalue())} bytes")
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
        print(f"[process_raw_upload] 파일 저장 완료: {saved_path}")

    dataframes = read_raw_file(file_bytes, extension)
    print(f"[process_raw_upload] 시트 로드 완료: {list(dataframes.keys())}")

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
    print(
        "[process_raw_upload] 시트 요약:",
        ", ".join(f"{summary['name']}({summary['rows']}행)" for summary in sheet_summaries),
    )

    conversations, normalized_records, normalized_path = normalize_conversations(dataframes)
    print(
        f"[process_raw_upload] 정규화 완료 - 대화 수: {len(conversations)}, CSV 경로: {normalized_path}"
    )

    return {
        "original_name": uploaded_file.name,
        "extension": extension,
        "uploaded_at": datetime.utcnow(),
        "saved_path": str(saved_path) if saved_path else None,
        "sheet_summaries": sheet_summaries,
        "dataframes": dataframes,
        "conversations": conversations,
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


def normalize_conversations(
    dataframes: Dict[str, pd.DataFrame]
) -> tuple[list[Conversation], list[Dict[str, Any]], Optional[str]]:
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
        return conversations, records, None

    NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    csv_path = NORMALIZED_DIR / f"conversations_{timestamp}.csv"
    df = pd.DataFrame(records)
    df.to_csv(csv_path, index=False)
    return conversations, records, str(csv_path)


def run_mock_batch_pipeline(library: SampleLibrary, count: int, use_llm: bool) -> Dict[str, Any]:
    MOCK_BATCH_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    batch_dir = MOCK_BATCH_DIR / f"run_{timestamp}"
    raw_dir = batch_dir / "raw"
    domain_dir = batch_dir / "domain"

    mock_api = MockChannelTalkAPI()
    user_chats_payload, messages_payloads = mock_api.fetch_user_chats(count=count)
    save_raw_payload(raw_dir, user_chats_payload, messages_payloads)
    conversations = load_conversations(raw_dir)
    domain_path, ids_path = save_domain_snapshot(conversations, domain_dir)

    settings = get_settings()
    retriever = SimilarityRetriever(
        top_k=settings.retrieval.sample_top_k,
        min_similarity=settings.retrieval.min_similarity,
    )
    llm_service = None
    if use_llm:
        st.write(
            f"LLM 호출 준비 - model={settings.llm.model_name}, temperature={settings.llm.temperature}, "
            f"OPENAI_API_KEY={'set' if os.getenv('OPENAI_API_KEY') else 'missing'}"
        )
        try:
            llm_service = LLMService(model=settings.llm.model_name, temperature=settings.llm.temperature)
        except Exception as exc:
            st.error(f"LLM 초기화 실패: {exc}")
            raise

    if settings.labels.schema:
        label_schema = [item.id for item in settings.labels.schema]
    else:
        label_schema = sorted({record.label_primary for record in library})

    pipeline = LabelingPipeline(retriever=retriever, llm_service=llm_service)
    st.write(f"라벨링 시작 - 대화 {len(conversations)}건, LLM 사용={bool(llm_service)}")
    result = pipeline.run(conversations, library, label_schema=label_schema)

    batch_dir.mkdir(parents=True, exist_ok=True)
    labels_path = batch_dir / "labels.json"
    labels_payload = {
        "generated_at": timestamp,
        "records": [serialize_label_record(record) for record in result.records],
        "failed": result.failed,
        "errors": result.errors,
    }
    labels_path.write_text(json.dumps(labels_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    df = label_records_to_dataframe(result.records)
    return {
        "timestamp": timestamp,
        "batch_dir": str(batch_dir),
        "raw_dir": str(raw_dir),
        "domain_path": str(domain_path),
        "ids_path": str(ids_path),
        "labels_path": str(labels_path),
        "count": len(conversations),
        "failed": result.failed,
        "errors": result.errors,
        "records": result.records,
        "labels_df": df,
        "conversations": conversations,
    }


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


def label_records_to_dataframe(records: List[LabelRecord]) -> pd.DataFrame:
    rows = []
    for record in records:
        rows.append(
            {
                "conversation_id": record.conversation_id,
                "label_primary": record.result.label_primary,
                "label_secondary": ", ".join(record.result.label_secondary),
                "confidence": record.result.confidence,
                "references": ", ".join(
                    f"{ref.sample_id}:{ref.label}({ref.score:.2f})" if ref.score is not None else f"{ref.sample_id}:{ref.label}"
                    for ref in record.result.references
                ),
                "created_at": record.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
    return pd.DataFrame(rows)


def serialize_label_record(record: LabelRecord) -> Dict[str, Any]:
    return {
        "conversation_id": record.conversation_id,
        "created_at": record.created_at.isoformat(),
        "label_primary": record.result.label_primary,
        "label_secondary": list(record.result.label_secondary),
        "confidence": record.result.confidence,
        "summary": record.result.summary,
        "reasoning": record.result.reasoning,
        "references": [
            {
                "sample_id": ref.sample_id,
                "label": ref.label,
                "score": ref.score,
                "summary": ref.summary,
            }
            for ref in record.result.references
        ],
    }


if __name__ == "__main__":
    main()
