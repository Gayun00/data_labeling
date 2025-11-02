from pathlib import Path

import streamlit as st
from openai import OpenAI

from src.llm_service import LLMService
from src.pipeline import run_labeling
from src.vector_store import VectorStore

st.set_page_config(page_title="Review Labeling MVP", layout="wide")

st.title("📮 Review Labeling MVP")
st.markdown("샘플 데이터와 신규 상담 CSV를 업로드하면 LLM을 사용해 자동으로 분류합니다.")

samples_file = st.file_uploader("샘플 CSV 업로드", type=["csv"], key="samples")
conversation_file = st.file_uploader("대화 CSV 업로드", type=["csv"], key="conversations")

if st.button("라벨링 실행"):
    if not samples_file or not conversation_file:
        st.error("샘플과 대화 CSV를 모두 업로드해야 합니다.")
    else:
        with st.spinner("LLM 라벨링 중..."):
            samples_path = Path("./data/samples/uploaded_samples.csv")
            convo_path = Path("./data/conversations/uploaded_conversations.csv")
            output_path = Path("./data/results/output.csv")
            samples_path.parent.mkdir(parents=True, exist_ok=True)
            convo_path.parent.mkdir(parents=True, exist_ok=True)
            samples_path.write_bytes(samples_file.read())
            convo_path.write_bytes(conversation_file.read())

            client = OpenAI()
            llm = LLMService()
            store = VectorStore()
            results = run_labeling(samples_path, convo_path, output_path, client, llm, store)

            st.success(f"총 {len(results)}건 라벨링 완료")
            st.download_button("결과 다운로드", output_path.read_bytes(), file_name="labels.csv", mime="text/csv")
