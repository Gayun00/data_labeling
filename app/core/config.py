"""Application configuration loading."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field, validator


class Settings(BaseModel):
    """Environment-driven configuration for the labeling app."""

    storage: Literal["local", "s3", "gcs"] = Field(default="local")
    bucket: Optional[str] = Field(default=None)
    region: Optional[str] = Field(default=None)
    tmp_dir: Path = Field(default=Path("./.tmp"))

    openai_api_key: Optional[str] = Field(default=None)
    embedding_model: str = Field(default="text-embedding-3-large")
    llm_model: str = Field(default="gpt-4o-mini")
    llm_backup_model: Optional[str] = Field(default="gpt-4.1-mini")

    max_llm_retries: int = Field(default=2, ge=0, le=5)
    llm_batch_size: int = Field(default=20, ge=1, le=200)
    neighbors_k: int = Field(default=3, ge=1, le=10)

    taxonomy_version: str = Field(default="v1")
    prompt_version: str = Field(default="v1")

    class Config:
        arbitrary_types_allowed = True

    @validator("bucket", always=True)
    def validate_bucket(cls, value: Optional[str], values: dict[str, object]) -> Optional[str]:
        if values.get("storage") != "local" and not value:
            raise ValueError("bucket is required when storage is not local")
        return value

    @validator("openai_api_key", always=True)
    def validate_api_key(cls, value: Optional[str]) -> Optional[str]:
        # We allow missing key for development, but the caller should check before API calls.
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load configuration from environment only once per process."""
    load_dotenv()
    return Settings(
        storage=os.getenv("STORAGE", "local").lower(),
        bucket=os.getenv("BUCKET"),
        region=os.getenv("REGION"),
        tmp_dir=Path(os.getenv("TMP_DIR", "./.tmp")),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-large"),
        llm_model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        llm_backup_model=os.getenv("LLM_BACKUP_MODEL", "gpt-4.1-mini"),
        max_llm_retries=int(os.getenv("LLM_MAX_RETRIES", "2")),
        llm_batch_size=int(os.getenv("LLM_BATCH_SIZE", "20")),
        neighbors_k=int(os.getenv("NEIGHBORS_K", "3")),
        taxonomy_version=os.getenv("TAXONOMY_VERSION", "v1"),
        prompt_version=os.getenv("PROMPT_VERSION", "v1"),
    )

