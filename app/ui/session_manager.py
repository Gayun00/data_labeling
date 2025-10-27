"""Lightweight session state helpers for Streamlit."""

from __future__ import annotations

import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import streamlit as st

from app.core.config import get_settings


@dataclass
class SessionJob:
    """Represents a labeling job tied to a Streamlit session."""

    job_id: str
    tmp_dir: Path
    chroma_namespace: str
    created_files: list[Path] = field(default_factory=list)

    def register_file(self, path: Path) -> None:
        """Remember a file for later cleanup."""
        self.created_files.append(path)

    def cleanup(self) -> None:
        """Remove temporary artifacts for this job."""
        for file_path in self.created_files:
            if file_path.exists():
                file_path.unlink(missing_ok=True)
        if self.tmp_dir.exists():
            shutil.rmtree(self.tmp_dir, ignore_errors=True)


def get_or_create_job() -> SessionJob:
    """Ensure the current session has an active job."""
    settings = get_settings()
    if "job" not in st.session_state:
        job_id = uuid.uuid4().hex[:8]
        tmp_dir = settings.tmp_dir / job_id
        tmp_dir.mkdir(parents=True, exist_ok=True)
        st.session_state["job"] = SessionJob(
            job_id=job_id,
            tmp_dir=tmp_dir,
            chroma_namespace=f"jobs/{job_id}",
        )
    return st.session_state["job"]


def reset_job() -> None:
    """Clear the current session job and delete its artifacts."""
    job: SessionJob | None = st.session_state.get("job")
    if job:
        job.cleanup()
    if "job" in st.session_state:
        del st.session_state["job"]

