"""Streamlit entry point for the review labeling MVP."""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

import pandas as pd
import streamlit as st

from app.core.config import get_settings
from app.ui.session_manager import get_or_create_job, reset_job

if TYPE_CHECKING:  # pragma: no cover - only used for type checking
    from streamlit.runtime.uploaded_file_manager import UploadedFile


def _render_file_preview(label: str, file: Optional["UploadedFile"]) -> None:
    """Show a small preview of an uploaded CSV."""
    if not file:
        st.write("파일이 업로드되면 미리보기가 표시됩니다.")
        return
    try:
        file.seek(0)
        df = pd.read_csv(file).head(5)
    except Exception as exc:  # noqa: BLE001
        st.error(f"{label} 파일을 읽는 중 오류가 발생했습니다: {exc}")
        return
    finally:
        file.seek(0)
    st.dataframe(df, use_container_width=True)


def main() -> None:
    """Render the Streamlit UI."""
    st.set_page_config(page_title="리뷰 자동 라벨링", layout="wide")
    settings = get_settings()
    job = get_or_create_job()

    st.title("리뷰 자동 라벨링 MVP")
    st.caption(
        "샘플 라벨 데이터를 기반으로 신규 리뷰를 자동 분류합니다. "
        "현재 버전은 기능 구성을 위한 프로토타입입니다."
    )

    with st.sidebar:
        st.subheader("세션 정보")
        st.write(f"작업 ID: `{job.job_id}`")
        st.write(f"저장소: `{settings.storage}`")
        if settings.storage != "local":
            st.write(f"버킷: `{settings.bucket}`")
            st.write(f"리전: `{settings.region}`")
        if st.button("세션 초기화", type="secondary"):
            reset_job()
            st.experimental_rerun()

    st.header("1. 샘플 라벨 데이터 업로드")
    sample_file = st.file_uploader(
        "라벨이 포함된 샘플 CSV 파일을 업로드하세요.",
        type=["csv"],
        key="sample_upload",
    )
    _render_file_preview("샘플", sample_file)

    st.header("2. 분석 대상 리뷰 업로드")
    review_file = st.file_uploader(
        "라벨링할 리뷰 CSV 파일을 업로드하세요.",
        type=["csv"],
        key="review_upload",
    )
    _render_file_preview("리뷰", review_file)

    st.header("3. 실행")
    st.info("자동 라벨링 엔진은 구현 중입니다. 다음 단계에서 기능이 추가될 예정입니다.")
    st.button("자동 라벨링 시작", disabled=True)

    st.header("4. 결과 다운로드")
    st.warning("라벨 결과는 아직 생성되지 않습니다. 구현이 완료되면 여기에 표시됩니다.")


if __name__ == "__main__":
    main()
