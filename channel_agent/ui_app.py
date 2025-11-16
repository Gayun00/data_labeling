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
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict

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


def run_pipeline(mock_mode: bool, created_from: str, created_to: str, disable_local_mask: bool) -> str:
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

    created_from = datetime.combine(start_date, datetime.min.time()).isoformat() + "Z"
    created_to = datetime.combine(end_date, datetime.max.time()).isoformat() + "Z"

    if st.button("파이프라인 실행", type="primary", key="run_pipeline"):
        with st.spinner("실행 중..."):
            try:
                output_path = run_pipeline(mock_mode, created_from, created_to, disable_local_mask)
                st.success(f"완료: {output_path}")
                if os.path.exists(output_path):
                    df = pd.read_csv(output_path)
                    st.dataframe(df, use_container_width=True)
                    st.download_button(
                        "CSV 다운로드",
                        data=df.to_csv(index=False),
                        file_name=os.path.basename(output_path),
                        mime="text/csv",
                        key="download_results",
                    )
                else:
                    st.warning("출력 파일을 찾을 수 없습니다.")
            except Exception as e:
                st.error(f"실행 실패: {e}")


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
