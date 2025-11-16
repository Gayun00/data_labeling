"""
Streamlit UI for ChannelTalk auto-labeler.
Features:
- 샘플 관리: CSV/엑셀 업로드/편집, 샘플 벡터 생성/검색(모의/실제 임베딩)
- 라벨링 실행: 목/실제 모드, few-shot 옵션, 결과/라벨/스킵 파일 미리보기 및 다운로드(통합 엑셀 포함)
- SQL 탭: DuckDB 메모리 쿼리
- 자연어 집계(룰 기반): 기간/강사 환불 비율 집계
"""
import os
import re
import sys
from ast import literal_eval
from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
import streamlit as st

# Ensure project root on path
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from channel_agent.agent import ChannelAgent
from channel_agent.channel_api import ChannelTalkClient
from channel_agent.config import ChannelTalkConfig, OpenAIConfig, PipelineConfig
from channel_agent.pipeline import ChannelLabelingPipeline
from channel_agent.sample_vectors import build_sample_index, search_sample_index

SAMPLES_DIR = "data/channel/samples"
SAMPLES_FILE = os.path.join(SAMPLES_DIR, "samples.csv")
RESULTS_DIR = "data/channel/results"
RESULT_FILE = "ui_labeled_chats.csv"


def normalize_labels(label_str: str) -> str:
    if pd.isna(label_str) or not str(label_str).strip():
        return ""
    parts = [p.strip() for p in str(label_str).replace("|", ",").split(",") if p.strip()]
    return "|".join(parts)


def samples_tab():
    st.markdown("### 샘플 관리 (text, labels)")
    st.markdown("- CSV/엑셀 업로드 시 컬럼명을 text, labels 로 맞춰주세요. 라벨은 , 또는 | 로 구분됩니다.")

    existing_df = pd.read_csv(SAMPLES_FILE) if os.path.exists(SAMPLES_FILE) else pd.DataFrame(columns=["text", "labels"])

    uploaded_file = st.file_uploader("샘플 CSV/엑셀 업로드 (선택)", type=["csv", "xlsx"], key="upload_samples")
    uploaded_df = None
    if uploaded_file:
        uploaded_df = pd.read_csv(uploaded_file) if uploaded_file.name.lower().endswith(".csv") else pd.read_excel(uploaded_file)
        uploaded_df = uploaded_df.rename(columns=str.lower)
        uploaded_df = uploaded_df[[c for c in uploaded_df.columns if c in ["text", "labels"]]]
        uploaded_df["labels"] = uploaded_df["labels"].apply(normalize_labels)
        st.success(f"업로드 {len(uploaded_df)}건 로드 완료")

    combined_df = existing_df if uploaded_df is None else pd.concat([existing_df, uploaded_df], ignore_index=True)

    st.subheader("샘플 편집")
    editable_df = st.data_editor(combined_df, num_rows="dynamic", use_container_width=True, key="samples_editor")

    if st.button("저장", type="primary", key="save_samples"):
        os.makedirs(SAMPLES_DIR, exist_ok=True)
        editable_df["labels"] = editable_df["labels"].apply(normalize_labels)
        editable_df.to_csv(SAMPLES_FILE, index=False)
        st.success(f"저장 완료: {SAMPLES_FILE}")

    st.markdown("### 샘플 벡터 인덱스")
    col_a, col_b = st.columns([2, 3])
    with col_a:
        use_mock_embed = st.checkbox("모의 임베딩 사용 (키/네트워크 없이)", value=True, key="use_mock_embed")
        if st.button("인덱스 생성/갱신", type="primary", key="build_index"):
            with st.spinner("인덱스 생성 중..."):
                try:
                    out = build_sample_index(use_mock_embeddings=use_mock_embed)
                    st.success(f"인덱스 생성 완료: {out}")
                except Exception as e:
                    st.error(f"실패: {e}")
    with col_b:
        query = st.text_input("유사도 검색 질의", value="", key="vector_query")
        top_k = st.slider("Top K", 1, 10, 5, 1, key="vector_topk")
        if st.button("검색", key="search_vectors"):
            try:
                results = search_sample_index(query, top_k=top_k, use_mock_embeddings=use_mock_embed)
                if not results:
                    st.info("결과가 없습니다.")
                else:
                    df_res = pd.DataFrame({"text": [r.text for r, _ in results],
                                           "labels": ["|".join(r.labels) for r, _ in results],
                                           "score": [score for _, score in results]})
                    st.dataframe(df_res, use_container_width=True)
            except Exception as e:
                st.error(f"검색 실패: {e}")


def run_pipeline(mock_mode: bool, created_from: str, created_to: str,
                 disable_local_mask: bool, use_sample_index: bool,
                 sample_use_mock_embed: bool, sample_top_k: int) -> str:
    agent = MockAgent() if mock_mode else ChannelAgent(OpenAIConfig(), ChannelTalkClient(ChannelTalkConfig()))
    channel_client = ChannelTalkClient(ChannelTalkConfig(access_key="mock", access_secret="mock")) if mock_mode else ChannelTalkClient(ChannelTalkConfig())
    pipeline = ChannelLabelingPipeline(
        channel_client,
        agent,
        PipelineConfig(output_dir=RESULTS_DIR, output_file=RESULT_FILE,
                       disable_local_mask=disable_local_mask,
                       use_sample_index=use_sample_index,
                       sample_use_mock_embeddings=sample_use_mock_embed,
                       sample_top_k=sample_top_k),
    )
    return pipeline.run(created_from, created_to)


class MockAgent:
    def summarize_and_label_dialog(self, dialog_text: str, agent_id: str = None) -> Dict[str, Any]:
        txt = dialog_text.lower()
        labels = []
        if "환불" in dialog_text or "refund" in txt:
            labels.append("환불")
        if "강사b" in txt:
            labels.append("강사B")
        if "강사a" in txt:
            labels.append("강사A")
        if "배송" in dialog_text:
            labels.append("배송")
        if not labels:
            labels.append("수강문의")
        return {"summary": dialog_text[:100], "labels": labels[:2], "emotion": "neutral"}


def pipeline_tab():
    st.markdown("### 채널톡 라벨링 실행")
    today = date.today()
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("시작일", value=today - timedelta(days=7), key="start_date")
    with col2:
        end_date = st.date_input("종료일", value=today, key="end_date")

    mock_mode = st.checkbox("모드: 목(Mock)으로 실행", value=True, key="mock_mode")
    disable_local_mask = st.checkbox("로컬 PII 마스킹 끄기", value=False, key="disable_mask")
    use_sample_index = st.checkbox("샘플 인덱스를 few-shot 프롬프트로 활용", value=True, key="use_sample_index")
    sample_use_mock_embed = st.checkbox("샘플 검색도 모의 임베딩 사용", value=True, key="sample_use_mock_embed")
    sample_top_k = st.slider("샘플 Top K", 1, 3, 1, 1, key="sample_top_k")

    created_from = datetime.combine(start_date, datetime.min.time()).isoformat() + "Z"
    created_to = datetime.combine(end_date, datetime.max.time()).isoformat() + "Z"

    df: Optional[pd.DataFrame] = st.session_state.get("results_df")
    output_path: Optional[str] = st.session_state.get("results_output_path")

    if st.button("파이프라인 실행", type="primary", key="run_pipeline"):
        with st.spinner("실행 중..."):
            try:
                output_path = run_pipeline(mock_mode, created_from, created_to, disable_local_mask,
                                           use_sample_index, sample_use_mock_embed, sample_top_k)
                if os.path.exists(output_path):
                    df = pd.read_csv(output_path)
                    st.session_state["results_df"] = df
                    st.session_state["results_output_path"] = output_path
                    st.success(f"완료: {output_path}")
                else:
                    st.warning("출력 파일을 찾을 수 없습니다.")
            except Exception as e:
                st.error(f"실행 실패: {e}")

    if df is not None:
        tab_choice = st.radio("보기", options=["결과 데이터", "라벨/태그 분석", "SQL/쿼리(내장)", "자연어 → 쿼리"], key="tab_selector")
        labels_path = Path(output_path).with_name("chat_labels.csv") if output_path else None
        skipped_path = Path(output_path).with_name("skipped_chats.csv") if output_path else None

        if tab_choice == "결과 데이터":
            st.dataframe(df, use_container_width=True)
            st.download_button("CSV 다운로드", data=df.to_csv(index=False), file_name=os.path.basename(output_path), mime="text/csv")
            col_a, col_b = st.columns(2)
            if labels_path and labels_path.exists():
                with col_a:
                    st.markdown("**chat_labels.csv**")
                    df_labels = pd.read_csv(labels_path)
                    st.dataframe(df_labels.head(200), use_container_width=True)
                    st.download_button("chat_labels.csv 다운로드", data=df_labels.to_csv(index=False), file_name=labels_path.name, mime="text/csv")
            if skipped_path and skipped_path.exists():
                with col_b:
                    st.markdown("**skipped_chats.csv**")
                    df_skipped = pd.read_csv(skipped_path)
                    st.dataframe(df_skipped.head(200), use_container_width=True)
                    st.download_button("skipped_chats.csv 다운로드", data=df_skipped.to_csv(index=False), file_name=skipped_path.name, mime="text/csv")
            # 통합 엑셀
            if labels_path and labels_path.exists():
                excel_buffer = BytesIO()
                with pd.ExcelWriter(excel_buffer, engine="xlsxwriter") as writer:
                    df.to_excel(writer, sheet_name="labeled_chats", index=False)
                    df_labels.to_excel(writer, sheet_name="chat_labels", index=False)
                    if skipped_path and skipped_path.exists():
                        df_skipped.to_excel(writer, sheet_name="skipped_chats", index=False)
                excel_buffer.seek(0)
                st.download_button("통합 엑셀 다운로드", data=excel_buffer.read(), file_name="channel_labeling_results.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        elif tab_choice == "라벨/태그 분석":
            df_work = df.copy()
            df_work["labels_list"] = df_work["labels"].fillna("").apply(lambda x: [p for p in str(x).split("|") if p])
            all_labels = sorted({lab for labs in df_work["labels_list"] for lab in labs})
            selected_labels = st.multiselect("라벨 필터", options=all_labels, default=all_labels)
            mode = st.radio("라벨 필터 모드", ["OR", "AND"], horizontal=True)
            if selected_labels:
                if mode == "AND":
                    df_work = df_work[df_work["labels_list"].apply(lambda labs: all(l in labs for l in selected_labels))]
                else:
                    df_work = df_work[df_work["labels_list"].apply(lambda labs: any(l in labs for l in selected_labels))]
            st.dataframe(df_work, use_container_width=True)
            lc = df_work.explode("labels_list")["labels_list"].value_counts().reset_index()
            lc.columns = ["label", "count"]
            st.dataframe(lc, use_container_width=True)

        elif tab_choice == "SQL/쿼리(내장)":
            st.markdown("라벨별 건수 예시: SELECT label, COUNT(DISTINCT chat_id) FROM chat_labels GROUP BY label")
            default_sql = "SELECT label, COUNT(DISTINCT chat_id) AS chats FROM chat_labels GROUP BY label ORDER BY chats DESC;"
            sql_text = st.text_area("SQL", value=default_sql, height=140)
            if labels_path and labels_path.exists():
                import duckdb
                con = duckdb.connect(database=":memory:")
                df_labels = pd.read_csv(labels_path).rename(columns={"user_chat_id": "chat_id"})
                df_chats_q = df.rename(columns={"user_chat_id": "chat_id"})
                con.register("chat_labels", df_labels)
                con.register("chats", df_chats_q)
                try:
                    res = con.execute(sql_text).fetch_df()
                    st.dataframe(res, use_container_width=True)
                except Exception as e:
                    st.error(f"쿼리 실패: {e}")

        elif tab_choice == "자연어 → 쿼리":
            st.markdown("자연어 입력: 예) 2024-08-01 ~ 2024-08-07 기간동안 A강사의 문의건 중 환불 문의 비율을 보여줘")
            labels_path = Path(output_path).with_name("chat_labels.csv")
            if not labels_path.exists():
                st.warning("chat_labels.csv를 찾을 수 없습니다.")
            else:
                nl_text = st.text_area("자연어 요청", value="2024-08-01 ~ 2024-08-07 기간동안 A강사의 문의건 중 환불 문의 비율을 보여줘", height=100)
                date_range = re.search(r"(20\d{2}-\d{2}-\d{2})\s*[~\-]\s*(20\d{2}-\d{2}-\d{2})", nl_text)
                start = date_range.group(1) if date_range else "2024-08-01"
                end = date_range.group(2) if date_range else "2024-08-07"
                teacher_match = re.search(r"강사\s*([A-Za-z가-힣0-9]+)", nl_text) or re.search(r"([A-Za-z가-힣0-9]+)\s*강사", nl_text)
                teacher = teacher_match.group(1) if teacher_match else "A"
                teacher_norm = f"강사{teacher}" if not str(teacher).startswith("강사") else str(teacher)

                teacher_like = f"%{teacher_norm.lower()}%"
                teacher_like_alt = f"%{teacher_norm.lower().replace('강사','')}강사%"
                sql_text = (
                    "WITH base AS (\n"
                    "  SELECT ch.chat_id, ch.created_at,\n"
                    "         BOOL_OR(lower(lb.label) LIKE '%환불%') AS is_refund,\n"
                    f"         BOOL_OR(lower(lb.label) LIKE '{teacher_like}' OR lower(lb.label) LIKE '{teacher_like_alt}') AS is_teacher\n"
                    "  FROM chats ch\n"
                    "  LEFT JOIN chat_labels lb ON lb.chat_id = ch.chat_id\n"
                    f"  WHERE coalesce(try_cast(ch.created_at AS TIMESTAMP), try_cast(ch.created_at || ' 00:00:00' AS TIMESTAMP)) >= '{start} 00:00:00' \n"
                    f"    AND coalesce(try_cast(ch.created_at AS TIMESTAMP), try_cast(ch.created_at || ' 00:00:00' AS TIMESTAMP)) <= '{end} 23:59:59'\n"
                    "  GROUP BY ch.chat_id, ch.created_at\n"
                    "),\n"
                    "counts AS (\n"
                    "  SELECT\n"
                    "    SUM(CASE WHEN is_teacher THEN 1 ELSE 0 END) AS teacher_total,\n"
                    "    SUM(CASE WHEN is_teacher AND is_refund THEN 1 ELSE 0 END) AS teacher_refunds\n"
                    "  FROM base\n"
                    ")\n"
                    "SELECT teacher_total, teacher_refunds,\n"
                    "  CASE WHEN teacher_total=0 THEN 0 ELSE teacher_refunds*100.0/teacher_total END AS teacher_refund_ratio\n"
                    "FROM counts;"
                )
                st.code(sql_text, language="sql")
                st.caption(f"인식된 기간: {start} ~ {end} / 강사: {teacher_norm}")

                import duckdb
                con = duckdb.connect(database=":memory:")
                df_labels = pd.read_csv(labels_path).rename(columns={"user_chat_id": "chat_id"})
                df_chats_q = df.rename(columns={"user_chat_id": "chat_id"})
                con.register("chat_labels", df_labels)
                con.register("chats", df_chats_q)
                try:
                    res = con.execute(sql_text).fetch_df()
                    st.dataframe(res, use_container_width=True)
                except Exception as e:
                    st.error(f"쿼리 실패: {e}")


def main() -> None:
    st.set_page_config(page_title="ChannelTalk 샘플/라벨러 UI", layout="wide")
    st.title("ChannelTalk 샘플 관리 & 라벨링")
    tab1, tab2 = st.tabs(["샘플 관리", "라벨링 실행"])
    with tab1:
        samples_tab()
    with tab2:
        pipeline_tab()


if __name__ == "__main__":
    main()
