"""Configuration loader for the ChannelTalk labeler."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field, PositiveInt, validator


CONFIG_PATH = Path("config/settings.yaml")


class LLMSettings(BaseModel):
    model_name: str = Field(..., alias="model_name")
    temperature: float = 0.0
    max_tokens: PositiveInt = 1024

    class Config:
        allow_population_by_field_name = True


class RetrievalSettings(BaseModel):
    sample_top_k: PositiveInt = 5
    min_similarity: float = 0.25

    @validator("min_similarity")
    def validate_similarity(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError("min_similarity must be between 0 and 1")
        return value


class LabelSchemaItem(BaseModel):
    id: str
    description: Optional[str] = None


class LabelSettings(BaseModel):
    schema: List[LabelSchemaItem]
    allow_secondary: bool = True

    @validator("schema")
    def validate_schema(cls, items: List[LabelSchemaItem]) -> List[LabelSchemaItem]:
        if not items:
            raise ValueError("label schema must contain at least one item")
        ids = [item.id for item in items]
        if len(ids) != len(set(ids)):
            raise ValueError("label schema contains duplicate ids")
        return items


class PipelineSettings(BaseModel):
    prompt_template: str = "default"
    max_messages_per_conversation: PositiveInt = 500


class Settings(BaseModel):
    llm: LLMSettings
    retrieval: RetrievalSettings
    labels: LabelSettings
    pipelines: PipelineSettings


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Settings file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


@lru_cache(maxsize=1)
def get_settings(path: Optional[Path] = None) -> Settings:
    """Load and cache application settings."""

    target_path = path or CONFIG_PATH
    raw = _load_yaml(target_path)
    return Settings.model_validate(raw)
