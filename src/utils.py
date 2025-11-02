"""공용 유틸 함수."""

from __future__ import annotations

from pathlib import Path


def ensure_exists(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


__all__ = ["ensure_exists"]
