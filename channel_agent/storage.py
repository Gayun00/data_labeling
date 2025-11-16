import csv
import os
from dataclasses import asdict, dataclass
from typing import List, Optional


@dataclass
class LabeledChat:
    user_chat_id: str
    summary: str
    labels: List[str]
    emotion: Optional[str]
    created_at: Optional[str] = None
    custom_fields: Optional[dict] = None


@dataclass
class SkippedChat:
    user_chat_id: str
    reason: str
    dialog: str


@dataclass
class FlatLabel:
    user_chat_id: str
    label: str


def ensure_output_dir(output_dir: str) -> None:
    os.makedirs(output_dir, exist_ok=True)


def save_results_csv(output_dir: str, filename: str, rows: List[LabeledChat]) -> str:
    ensure_output_dir(output_dir)
    path = os.path.join(output_dir, filename)
    fieldnames = ["user_chat_id", "summary", "labels", "emotion", "created_at", "custom_fields"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            payload = asdict(row)
            payload["labels"] = "|".join(payload.get("labels") or [])
            writer.writerow(payload)
    return path


def save_skipped_csv(output_dir: str, filename: str, rows: List[SkippedChat]) -> str:
    ensure_output_dir(output_dir)
    path = os.path.join(output_dir, filename)
    fieldnames = ["user_chat_id", "reason", "dialog"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            payload = asdict(row)
            writer.writerow(payload)
    return path


def save_flat_labels_csv(output_dir: str, filename: str, rows: List[FlatLabel]) -> str:
    ensure_output_dir(output_dir)
    path = os.path.join(output_dir, filename)
    fieldnames = ["user_chat_id", "label"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            payload = asdict(row)
            writer.writerow(payload)
    return path
