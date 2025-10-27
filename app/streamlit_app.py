"""Streamlit entry point for the review labeling MVP."""

from __future__ import annotations

from typing import Callable, Iterable, Mapping, Optional, TYPE_CHECKING

import pandas as pd
import streamlit as st

from app.core import data_loader
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


PLACEHOLDER_OPTION = "-- 선택 --"


def _reset_mapping_state(mapping_key: str, field_names: Iterable[str]) -> None:
    """Clear widget state for mapping select boxes."""
    for field in field_names:
        widget_key = f"{mapping_key}:{field}"
        if widget_key in st.session_state:
            del st.session_state[widget_key]


def _clear_dataset_state(dataset_key: str, mapping_key: str, validity_key: str, field_labels: Mapping[str, str]) -> None:
    """Remove dataset and related mapping state from the session."""
    st.session_state.pop(dataset_key, None)
    st.session_state.pop(mapping_key, None)
    st.session_state.pop(validity_key, None)
    _reset_mapping_state(mapping_key, field_labels.keys())


def _sync_uploaded_dataset(
    section: str,
    uploaded_file: Optional["UploadedFile"],
    dataset_key: str,
    mapping_key: str,
    loader: Callable,
    field_labels: Mapping[str, str],
) -> Optional[pd.DataFrame]:
    """Load uploaded CSVs and keep session state in sync."""
    validity_key = f"{section}_mapping_valid"
    file_id_key = f"{section}_file_id"
    if not uploaded_file:
        _clear_dataset_state(dataset_key, mapping_key, validity_key, field_labels)
        st.session_state.pop(file_id_key, None)
        return None

    current_id = st.session_state.get(file_id_key)
    uploaded_id = f"{uploaded_file.name}:{uploaded_file.size}"
    if current_id != uploaded_id:
        try:
            loaded = loader(uploaded_file)
        except Exception as exc:  # noqa: BLE001
            st.error(f"{section} 데이터를 처리하는 중 오류가 발생했습니다: {exc}")
            _clear_dataset_state(dataset_key, mapping_key, validity_key, field_labels)
            st.session_state.pop(file_id_key, None)
            return None
        st.session_state[dataset_key] = loaded.dataframe
        st.session_state[mapping_key] = dict(loaded.inferred_mapping)
        st.session_state[file_id_key] = uploaded_id
        _reset_mapping_state(mapping_key, field_labels.keys())
    return st.session_state.get(dataset_key)


def _render_mapping_controls(
    title: str,
    dataset_key: str,
    mapping_key: str,
    validity_key: str,
    field_labels: Mapping[str, str],
) -> None:
    """Render select boxes for mapping CSV columns to logical fields."""
    df: Optional[pd.DataFrame] = st.session_state.get(dataset_key)
    if df is None:
        return

    current_mapping = dict.fromkeys(field_labels.keys(), "")
    current_mapping.update(st.session_state.get(mapping_key, {}))
    columns = df.columns.tolist()

    st.subheader(title)
    with st.container():
        updated_mapping: dict[str, str] = {}
        for field, label in field_labels.items():
            options = [PLACEHOLDER_OPTION, *columns]
            current_value = current_mapping.get(field, "")
            if current_value not in columns:
                current_value = ""
            default_index = options.index(current_value) if current_value else 0
            selection = st.selectbox(
                label,
                options,
                index=default_index,
                key=f"{mapping_key}:{field}",
            )
            updated_mapping[field] = "" if selection == PLACEHOLDER_OPTION else selection

    missing, duplicates = data_loader.validate_mapping(updated_mapping, columns)
    st.session_state[mapping_key] = updated_mapping
    st.session_state[validity_key] = not missing and not duplicates

    status_container = st.container()
    if missing:
        missing_labels = [field_labels[field] for field in missing if field in field_labels]
        status_container.error(f"매핑되지 않은 필수 필드: {', '.join(missing_labels)}")
    if duplicates:
        status_container.warning(f"중복으로 선택된 컬럼: {', '.join(sorted(set(duplicates)))}")
    if not missing and not duplicates:
        status_container.success("필수 필드가 모두 매핑되었습니다.")


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
    sample_df = _sync_uploaded_dataset(
        section="sample",
        uploaded_file=sample_file,
        dataset_key="sample_df",
        mapping_key="sample_mapping",
        loader=data_loader.load_sample_dataset,
        field_labels=data_loader.SAMPLE_FIELD_LABELS,
    )
    if sample_df is not None:
        st.success(f"샘플 데이터 {len(sample_df):,}건 로드 · 컬럼 {len(sample_df.columns)}개")
        _render_mapping_controls(
            title="샘플 컬럼 매핑",
            dataset_key="sample_df",
            mapping_key="sample_mapping",
            validity_key="sample_mapping_valid",
            field_labels=data_loader.SAMPLE_FIELD_LABELS,
        )

    st.header("2. 분석 대상 리뷰 업로드")
    review_file = st.file_uploader(
        "라벨링할 리뷰 CSV 파일을 업로드하세요.",
        type=["csv"],
        key="review_upload",
    )
    _render_file_preview("리뷰", review_file)
    review_df = _sync_uploaded_dataset(
        section="review",
        uploaded_file=review_file,
        dataset_key="review_df",
        mapping_key="review_mapping",
        loader=data_loader.load_review_dataset,
        field_labels=data_loader.REVIEW_FIELD_LABELS,
    )
    if review_df is not None:
        st.success(f"리뷰 데이터 {len(review_df):,}건 로드 · 컬럼 {len(review_df.columns)}개")
        _render_mapping_controls(
            title="리뷰 컬럼 매핑",
            dataset_key="review_df",
            mapping_key="review_mapping",
            validity_key="review_mapping_valid",
            field_labels=data_loader.REVIEW_FIELD_LABELS,
        )

    st.header("3. 실행")
    st.info("자동 라벨링 엔진은 구현 중입니다. 다음 단계에서 기능이 추가될 예정입니다.")
    st.button("자동 라벨링 시작", disabled=True)

    st.header("4. 결과 다운로드")
    st.warning("라벨 결과는 아직 생성되지 않습니다. 구현이 완료되면 여기에 표시됩니다.")


if __name__ == "__main__":
    main()
