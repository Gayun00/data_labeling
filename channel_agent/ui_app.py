"""
Streamlit UI for ChannelTalk auto-labeler.

Tabs:
- 샘플 관리: CSV/엑셀 업로드 또는 직접 입력으로 text, labels 편집/저장
- 파이프라인 실행: 날짜 범위 선택 후 채널톡 데이터(현재 목) 수집→라벨링→미리보기/다운로드

Run:
    streamlit run channel_agent/ui_app.py
"""

import os
import sys
from ast import literal_eval
from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
import streamlit as st

# Ensure project root is on sys.path when run via `streamlit run`.
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from channel_agent.agent import ChannelAgent
from channel_agent.channel_api import ChannelTalkClient
from channel_agent.config import ChannelTalkConfig, OpenAIConfig, PipelineConfig
from channel_agent.pipeline import ChannelLabelingPipeline
from channel_agent.sample_vectors import build_sample_index, search_sample_index, VECTORS_FILE

SAMPLES_DIR = "data/channel/samples"
SAMPLES_FILE = os.path.join(SAMPLES_DIR, "samples.csv")
RESULTS_DIR = "data/channel/results"
RESULT_FILE = "ui_labeled_chats.csv"


def load_existing_samples() -> pd.DataFrame:
    if os.path.exists(SAMPLES_FILE):
        return pd.read_csv(SAMPLES_FILE)
    return pd.DataFrame(columns=["text", "labels"])


def normalize_labels(label_str: str) -> str:
    if pd.isna(label_str) or not str(label_str).strip():
        return ""
    parts = [part.strip() for part in str(label_str).replace("|", ",").split(",")]
    parts = [p for p in parts if p]
    return "|".join(parts)


class MockAgent:
    """간단한 키워드 기반 목 라벨러 (네트워크/키 필요 없음)."""

    def summarize_and_label_dialog(self, dialog_text: str, agent_id: str = None) -> Dict[str, Any]:
        txt = dialog_text.lower()
        labels = []
        if "배송" in dialog_text or "ship" in txt:
            labels.append("배송")
        if "환불" in dialog_text or "refund" in txt:
            labels.append("환불")
        if "버그" in dialog_text or "오류" in dialog_text or "bug" in txt:
            labels.append("버그")
        if not labels:
            labels.append("일반문의")
        return {
            "summary": dialog_text[:100] + ("..." if len(dialog_text) > 100 else ""),
            "labels": labels,
            "emotion": "neutral",
        }


def run_pipeline(
    mock_mode: bool,
    created_from: str,
    created_to: str,
    disable_local_mask: bool,
    use_sample_index: bool,
    sample_use_mock_embed: bool,
    sample_top_k: int,
) -> str:
    if mock_mode:
        channel_client = ChannelTalkClient(ChannelTalkConfig(access_key="mock", access_secret="mock"))
        agent = MockAgent()
    else:
        channel_client = ChannelTalkClient(ChannelTalkConfig())
        agent = ChannelAgent(OpenAIConfig(), channel_client)

    pipeline = ChannelLabelingPipeline(
        channel_client,
        agent,
        PipelineConfig(
            output_dir=RESULTS_DIR,
            output_file=RESULT_FILE,
            disable_local_mask=disable_local_mask,
            use_sample_index=use_sample_index,
            sample_use_mock_embeddings=sample_use_mock_embed,
            sample_top_k=sample_top_k,
        ),
    )
    return pipeline.run(created_from, created_to)


def samples_tab():
    st.markdown("### 샘플 관리 (text, labels)")
    st.markdown(
        "- CSV/엑셀 업로드 시 컬럼명을 `text`, `labels` 로 맞춰주세요. "
        "여러 라벨은 `,` 또는 `|` 로 구분합니다."
    )

    existing_df = load_existing_samples()

    uploaded_file = st.file_uploader("샘플 CSV/엑셀 업로드 (선택)", type=["csv", "xlsx"], key="upload_samples")
    uploaded_df = None
    if uploaded_file:
        if uploaded_file.name.lower().endswith(".csv"):
            uploaded_df = pd.read_csv(uploaded_file)
        else:
            uploaded_df = pd.read_excel(uploaded_file)

        uploaded_df = uploaded_df.rename(columns=str.lower)
        uploaded_df = uploaded_df[[col for col in uploaded_df.columns if col in ["text", "labels"]]]
        uploaded_df["labels"] = uploaded_df["labels"].apply(normalize_labels)
        st.success(f"업로드 {len(uploaded_df)}건 로드 완료")

    combined_df = existing_df
    if uploaded_df is not None:
        combined_df = pd.concat([existing_df, uploaded_df], ignore_index=True)

    st.subheader("샘플 편집")
    st.markdown("행을 직접 추가/수정 후 저장하세요. 라벨은 `,` 또는 `|` 로 구분.")
    editable_df = st.data_editor(
        combined_df,
        num_rows="dynamic",
        use_container_width=True,
        key="samples_editor",
    )

    if st.button("저장", type="primary", key="save_samples"):
        os.makedirs(SAMPLES_DIR, exist_ok=True)
        editable_df["labels"] = editable_df["labels"].apply(normalize_labels)
        editable_df.to_csv(SAMPLES_FILE, index=False)
        st.success(f"저장 완료: {SAMPLES_FILE}")

    st.markdown("### 샘플 벡터 인덱스")
    st.caption("샘플을 임베딩해 간단한 유사도 검색을 할 수 있습니다. 네트워크/키 없이 테스트하려면 모의 임베딩을 사용하세요.")
    col_a, col_b = st.columns([2, 3])
    with col_a:
        use_mock_embed = st.checkbox("모의 임베딩 사용 (키/네트워크 없이)", value=True, key="use_mock_embed")
        build_btn = st.button("인덱스 생성/갱신", type="primary", key="build_index")
    status_placeholder = st.empty()

    if build_btn:
        with st.spinner("인덱스 생성 중..."):
            try:
                out = build_sample_index(use_mock_embeddings=use_mock_embed)
                status_placeholder.success(f"인덱스 생성 완료: {out}")
            except Exception as e:
                status_placeholder.error(f"실패: {e}")

    with col_b:
        query = st.text_input("유사도 검색 질의", value="", key="vector_query")
        top_k = st.slider("Top K", min_value=1, max_value=10, value=5, step=1, key="vector_topk")
        if st.button("검색", key="search_vectors"):
            try:
                results = search_sample_index(query, top_k=top_k, use_mock_embeddings=use_mock_embed)
                if not results:
                    st.info("결과가 없습니다.")
                else:
                    df_res = pd.DataFrame(
                        [{"text": r.text, "labels": "|".join(r.labels), "score": score} for r, score in results]
                    )
                    st.dataframe(df_res, use_container_width=True)
            except Exception as e:
                st.error(f"검색 실패: {e}")


def pipeline_tab():
    st.markdown("### 채널톡 라벨링 실행")
    st.markdown(
        "날짜 범위를 선택하고 실행하세요. 현재 기본은 목 모드(실제 API/LLM 호출 없이 동작)입니다."
    )

    today = date.today()
    default_from = today - timedelta(days=7)
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("시작일", value=default_from, key="start_date")
    with col2:
        end_date = st.date_input("종료일", value=today, key="end_date")

    mock_mode = st.checkbox("모드: 목(Mock)으로 실행 (키/네트워크 없이)", value=True, key="mock_mode")
    st.caption("실제 호출을 원하면 체크 해제 후 .env에 키 설정 및 네트워크 허용이 필요합니다.")

    disable_local_mask = st.checkbox(
        "로컬 PII 마스킹 끄기 (에이전트 가드레일 테스트용)", value=False, key="disable_mask"
    )
    st.caption("끄면 전화/계좌/주소가 그대로 전달되어 에이전트/가드레일이 마스킹하는지 테스트할 수 있습니다.")

    st.markdown("#### 샘플 few-shot 설정")
    use_sample_index = st.checkbox("샘플 인덱스를 few-shot 프롬프트로 활용", value=True, key="use_sample_index")
    sample_use_mock_embed = st.checkbox(
        "샘플 검색도 모의 임베딩 사용(인덱스 생성 모드와 맞춰주세요)", value=True, key="sample_use_mock_embed"
    )
    sample_top_k = st.slider("샘플 Top K", min_value=1, max_value=5, value=3, step=1, key="sample_top_k")
    st.caption("샘플 인덱스가 없으면 자동으로 건너뜁니다. 샘플 탭에서 인덱스를 먼저 생성하세요.")

    created_from = datetime.combine(start_date, datetime.min.time()).isoformat() + "Z"
    created_to = datetime.combine(end_date, datetime.max.time()).isoformat() + "Z"

    # 세션 상태에서 최근 결과 복원
    df: Optional[pd.DataFrame] = st.session_state.get("results_df")
    output_path: Optional[str] = st.session_state.get("results_output_path")

    if st.button("파이프라인 실행", type="primary", key="run_pipeline"):
        with st.spinner("실행 중..."):
            try:
                output_path = run_pipeline(
                    mock_mode,
                    created_from,
                    created_to,
                    disable_local_mask,
                    use_sample_index,
                    sample_use_mock_embed,
                    sample_top_k,
                )
                st.success(f"완료: {output_path}")
                if os.path.exists(output_path):
                    df = pd.read_csv(output_path)
                    st.session_state["results_df"] = df
                    st.session_state["results_output_path"] = output_path
                else:
                    st.warning("출력 파일을 찾을 수 없습니다.")
            except Exception as e:
                st.error(f"실행 실패: {e}")

    # 분석/다운로드를 별도 뷰로 분리 (라디오 사용: 선택 상태 유지)
    if df is not None:
        current_tab = st.session_state.get("active_tab", "결과 데이터")
        tab_choice = st.radio(
            "보기",
            options=["결과 데이터", "라벨/태그 분석", "SQL/쿼리(내장)", "자연어 → 쿼리(준비 중)"],
            index=["결과 데이터", "라벨/태그 분석", "SQL/쿼리(내장)", "자연어 → 쿼리(준비 중)"].index(current_tab) if current_tab in ["결과 데이터", "라벨/태그 분석", "SQL/쿼리(내장)", "자연어 → 쿼리(준비 중)"] else 0,
            horizontal=True,
            key="tab_selector",
        )
        st.session_state["active_tab"] = tab_choice

        if tab_choice == "결과 데이터":
            st.dataframe(df, use_container_width=True)
            st.download_button(
                "CSV 다운로드",
                data=df.to_csv(index=False),
                file_name=os.path.basename(output_path),
                mime="text/csv",
                key="download_results_all",
            )
            # Flat labels/Skipped preview if available
            labels_path = Path(output_path).with_name("chat_labels.csv")
            skipped_path = Path(output_path).with_name("skipped_chats.csv")
            col_a, col_b = st.columns(2)
            with col_a:
                if labels_path.exists():
                    st.markdown("**chat_labels.csv (라벨 explode)**")
                    df_labels = pd.read_csv(labels_path)
                    st.dataframe(df_labels.head(200), use_container_width=True)
                    st.download_button(
                        "chat_labels.csv 다운로드",
                        data=df_labels.to_csv(index=False),
                        file_name=labels_path.name,
                        mime="text/csv",
                        key="download_labels",
                    )
            with col_b:
                if skipped_path.exists():
                    st.markdown("**skipped_chats.csv (off-topic/abuse)**")
                    df_skipped = pd.read_csv(skipped_path)
                    st.dataframe(df_skipped.head(200), use_container_width=True)
                    st.download_button(
                        "skipped_chats.csv 다운로드",
                        data=df_skipped.to_csv(index=False),
                        file_name=skipped_path.name,
                        mime="text/csv",
                        key="download_skipped",
                    )
            # 통합 Excel 다운로드 (시트 분리)
            if labels_path.exists() or skipped_path.exists():
                excel_buffer = BytesIO()
                with pd.ExcelWriter(excel_buffer, engine="xlsxwriter") as writer:
                    df.to_excel(writer, sheet_name="labeled_chats", index=False)
                    if labels_path.exists():
                        df_labels.to_excel(writer, sheet_name="chat_labels", index=False)
                    if skipped_path.exists():
                        df_skipped.to_excel(writer, sheet_name="skipped_chats", index=False)
                excel_buffer.seek(0)
                st.download_button(
                    "통합 엑셀 다운로드 (시트별)",
                    data=excel_buffer.read(),
                    file_name="channel_labeling_results.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="download_excel_combined",
                )
        elif tab_choice == "라벨/태그 분석":
            st.markdown("#### 라벨/태그 필터 및 통계")
            df["labels_list"] = df["labels"].fillna("").apply(
                lambda x: [p for p in str(x).split("|") if p]
            )

            def parse_tags(val: Any) -> list:
                try:
                    obj = literal_eval(val) if isinstance(val, str) else val
                    if isinstance(obj, dict):
                        return [
                            t.get("name")
                            for t in obj.get("tags", [])
                            if isinstance(t, dict)
                        ]
                except Exception:
                    return []
                return []

            if "custom_fields" in df.columns:
                df["tags_list"] = df["custom_fields"].apply(parse_tags)
            else:
                df["tags_list"] = [[] for _ in range(len(df))]

            all_labels = sorted({lab for labs in df["labels_list"] for lab in labs})
            selected_labels = st.multiselect("라벨 필터", options=all_labels, default=all_labels, key="label_filter_select")
            filter_mode = st.radio("라벨 필터 모드", options=["합집합(OR)", "교집합(AND)"], horizontal=True, key="label_filter_mode")

            filtered = df
            if selected_labels:
                if filter_mode == "교집합(AND)":
                    filtered = df[df["labels_list"].apply(lambda labs: all(l in labs for l in selected_labels))]
                else:
                    filtered = df[df["labels_list"].apply(lambda labs: any(l in labs for l in selected_labels))]

            st.markdown("**필터 적용 테이블**")
            st.dataframe(filtered, use_container_width=True)

            st.markdown("**라벨별 건수**")
            label_counts_series = filtered.explode("labels_list")["labels_list"].value_counts()
            label_counts = label_counts_series.reset_index()
            label_counts.columns = ["label", "count"]
            st.dataframe(label_counts, use_container_width=True)

            st.markdown("**라벨 x 태그 매트릭스(있으면)**")
            if filtered["tags_list"].apply(len).sum() > 0:
                exploded = filtered.explode("labels_list").explode("tags_list")
                pivot = (
                    exploded.pivot_table(
                        index="labels_list", columns="tags_list", aggfunc="size", fill_value=0
                    )
                    if not exploded.empty
                    else pd.DataFrame()
                )
                st.dataframe(pivot, use_container_width=True)

            st.download_button(
                "CSV (필터 적용) 다운로드",
                data=filtered.drop(columns=["labels_list", "tags_list"], errors="ignore").to_csv(index=False),
                file_name=f"filtered_{os.path.basename(output_path) if output_path else 'results.csv'}",
                mime="text/csv",
                key="download_results_filtered",
            )
        elif tab_choice == "SQL/쿼리(내장)":
            st.markdown("#### 간단 SQL 쿼리 (데모용, CSV를 메모리에 로드해 실행)")
            default_query = (
                "SELECT label, COUNT(DISTINCT chat_id) AS chats "
                "FROM chat_labels GROUP BY label ORDER BY chats DESC LIMIT 20;"
            )
            query = st.text_area("SQL 입력", value=default_query, height=140, key="sql_input")
            labels_path = Path(output_path).with_name("chat_labels.csv")
            if not labels_path.exists():
                st.warning("chat_labels.csv를 찾을 수 없습니다. 라벨링을 한 번 실행한 뒤 사용하세요.")
            else:
                import duckdb

                con = duckdb.connect(database=":memory:")
                df_labels = pd.read_csv(labels_path)
                con.register("chat_labels", df_labels)
                con.register("chats", df)

                try:
                    res = con.execute(query).fetch_df()
                    st.dataframe(res, use_container_width=True)
                except Exception as e:
                    st.error(f"쿼리 실패: {e}")

        elif tab_choice == "자연어 → 쿼리(준비 중)":
            st.markdown(
                "자연어를 SQL/피벗으로 변환하는 기능은 추후 모델 연동 시 활성화 예정입니다.\n"
                "예: '강사A와 환불 라벨을 모두 가진 대화만 날짜별로 집계해줘' → SQL로 변환"
            )


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
