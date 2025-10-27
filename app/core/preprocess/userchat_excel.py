"""Utilities to reshape multi-sheet ChannelTalk exports into a single table."""

from __future__ import annotations

import io
import re
from typing import Iterable, Mapping, Optional

import numpy as np
import pandas as pd

from app.core.data_loader import DataValidationError

# Expected sheet names in the exported workbook
USERCHAT_SHEET = "UserChat data"
MESSAGE_SHEET = "Message data"
TAG_SHEET = "UserChatTag data"
USER_SHEET = "User data"


def is_userchat_workbook(sheet_names: Iterable[str]) -> bool:
    """Heuristically check whether the workbook contains expected sheets."""
    sheet_set = {name.strip().lower() for name in sheet_names}
    return USERCHAT_SHEET.lower() in sheet_set and MESSAGE_SHEET.lower() in sheet_set


def read_userchat_workbook(uploaded_file) -> Mapping[str, pd.DataFrame]:
    """Read all sheets from an uploaded Excel file into dataframes."""
    uploaded_file.seek(0)
    buffer = io.BytesIO(uploaded_file.read())
    uploaded_file.seek(0)
    try:
        sheets = pd.read_excel(buffer, sheet_name=None)
    except ImportError as exc:  # pragma: no cover - depends on optional dep
        raise DataValidationError(
            "엑셀 파일을 읽으려면 `openpyxl` 패키지가 필요합니다. "
            "`pip install openpyxl`로 설치한 뒤 다시 시도해 주세요."
        ) from exc
    if not sheets:
        raise DataValidationError("업로드한 엑셀에서 데이터를 찾을 수 없습니다.")
    return sheets


def build_userchat_table(sheets: Mapping[str, pd.DataFrame], sample_n: Optional[int] = None) -> pd.DataFrame:
    """Aggregate data from ChannelTalk workbook into a single labeling-friendly table."""
    df_chat = _get_sheet(sheets, USERCHAT_SHEET)
    if df_chat is None or df_chat.empty:
        raise DataValidationError("필수 시트 'UserChat data'가 비어 있거나 없습니다.")

    df_msg = _get_sheet(sheets, MESSAGE_SHEET)
    df_tag = _get_sheet(sheets, TAG_SHEET)
    df_user = _get_sheet(sheets, USER_SHEET)

    chat_id_col = _find_col(df_chat, [r"(user.?chat.*id$|thread_?id$|chat_?id$|^id$)"])
    created_col = _find_col(df_chat, [r"(created.*at|createdAt|created_at)"])
    channel_col = _find_col(df_chat, [r"(^channel$|channelName)"])
    service_col = _find_col(df_chat, [r"(service|product|brand)"])
    csat_col = _find_col(df_chat, [r"(csat$|profile\.csat)"])
    csat_comment_col = _find_col(df_chat, [r"(csat.*comment|profile\.csatComment)"])
    user_hash_col = _find_col(df_chat, [r"(user.*hash|user.*hashed|userHash)"])

    if chat_id_col is None:
        raise DataValidationError("스레드 ID를 찾을 수 없습니다. 'UserChat data' 시트를 확인해 주세요.")

    base_cols = [chat_id_col]
    for col in [created_col, channel_col, service_col, user_hash_col, csat_col, csat_comment_col]:
        if col and col in df_chat.columns:
            base_cols.append(col)

    base = df_chat[base_cols].copy()
    base = base.rename(columns={chat_id_col: "thread_id"})

    if created_col and created_col in base.columns:
        base["created_at"] = pd.to_datetime(base.pop(created_col), errors="coerce")
    else:
        base["created_at"] = pd.NaT

    rename_map: dict[str, str] = {}
    if channel_col and channel_col in base.columns:
        rename_map[channel_col] = "channel"
    if service_col and service_col in base.columns:
        rename_map[service_col] = "service"
    if user_hash_col and user_hash_col in base.columns:
        rename_map[user_hash_col] = "user_id_hash"
    if csat_col and csat_col in base.columns:
        rename_map[csat_col] = "csat"
    if csat_comment_col and csat_comment_col in base.columns:
        rename_map[csat_comment_col] = "csat_comment"
    base = base.rename(columns=rename_map)

    for column in ["channel", "service", "user_id_hash", "csat", "csat_comment"]:
        if column not in base.columns:
            base[column] = "" if column != "csat" else np.nan

    msg_agg = _aggregate_messages(df_msg)
    tag_agg = _aggregate_tags(df_tag)
    lang_agg = _extract_user_lang(df_user, df_chat, chat_id_col=chat_id_col)

    joined = base.merge(msg_agg, on="thread_id", how="left")
    if not tag_agg.empty:
        joined = joined.merge(tag_agg, on="thread_id", how="left")
    if not lang_agg.empty:
        joined = joined.merge(lang_agg, on="thread_id", how="left")

    required_columns = [
        "message_first",
        "message_last",
        "message_concat",
    ]
    for col in required_columns:
        if col not in joined.columns:
            joined[col] = ""

    label_columns = [
        "summary",
        "category",
        "subtopic",
        "intent",
        "sentiment",
        "urgency",
        "issue_type",
        "language",
        "resolution_type",
        "next_action",
        "spam",
        "confidence",
        "evidence_spans",
        "notes",
    ]
    for col in label_columns:
        if col not in joined.columns:
            if col == "spam":
                joined[col] = False
            elif col == "confidence":
                joined[col] = np.nan
            else:
                joined[col] = ""

    ordered_columns = [
        "thread_id",
        "created_at",
        "channel",
        "service",
        "user_id_hash",
        "csat",
        "csat_comment",
        "message_first",
        "message_last",
        "message_concat",
        "summary",
        "category",
        "subtopic",
        "intent",
        "sentiment",
        "urgency",
        "issue_type",
        "language",
        "resolution_type",
        "next_action",
        "spam",
        "confidence",
        "evidence_spans",
        "notes",
    ]

    existing_order = [col for col in ordered_columns if col in joined.columns]
    remaining = [col for col in joined.columns if col not in existing_order]
    result = joined[existing_order + remaining]

    if sample_n is not None:
        result = result.head(sample_n).copy()
    return result


# ----- Helpers ----------------------------------------------------------------


def _find_col(df: Optional[pd.DataFrame], patterns: Iterable[str]) -> Optional[str]:
    if df is None or df.empty:
        return None
    for pattern in patterns:
        regex = re.compile(pattern, re.IGNORECASE)
        for column in df.columns:
            if regex.search(str(column)):
                return column
    return None


def _safe_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).replace("\n", " ").strip()


def _aggregate_messages(df_msg: Optional[pd.DataFrame]) -> pd.DataFrame:
    if df_msg is None or df_msg.empty:
        return pd.DataFrame(columns=["thread_id", "message_first", "message_last", "message_concat"])

    thread_col = _find_col(df_msg, [r"(user.?chat.*id$|thread_?id$|chat_?id$|^userChatId$)"])
    text_col = _find_col(df_msg, [r"(text|body|content|message)$"])
    created_col = _find_col(df_msg, [r"(created|sent).*at", r"(timestamp|time)"])

    if not thread_col or not text_col:
        return pd.DataFrame(columns=["thread_id", "message_first", "message_last", "message_concat"])

    columns = [thread_col, text_col]
    if created_col and created_col in df_msg.columns:
        columns.append(created_col)
    temp = df_msg[columns].copy()
    temp[text_col] = temp[text_col].map(_safe_text)

    if created_col and created_col in temp.columns:
        temp[created_col] = pd.to_datetime(temp[created_col], errors="coerce")
        temp = temp.sort_values([thread_col, created_col])
    else:
        temp = temp.sort_values([thread_col])

    grouped = temp.groupby(thread_col)
    first_last = grouped[text_col].agg(["first", "last"]).rename(columns={"first": "message_first", "last": "message_last"})

    def _concat_messages(group: pd.DataFrame) -> str:
        texts = group[text_col].tolist()
        head = texts[:3]
        tail = texts[-1:] if len(texts) > 3 else []
        combined = head + tail
        return " || ".join(combined)[:2000]

    concat_series = grouped.apply(_concat_messages)

    result = first_last.merge(concat_series.rename("message_concat"), left_index=True, right_index=True).reset_index()
    return result.rename(columns={thread_col: "thread_id"})


def _aggregate_tags(df_tag: Optional[pd.DataFrame]) -> pd.DataFrame:
    if df_tag is None or df_tag.empty:
        return pd.DataFrame(columns=["thread_id", "tags"])

    thread_col = _find_col(df_tag, [r"(user.?chat.*id$|thread_?id$|chat_?id$|^userChatId$)"])
    tag_col = _find_col(df_tag, [r"(tag.?name|tag|label)"])
    if not thread_col or not tag_col:
        return pd.DataFrame(columns=["thread_id", "tags"])

    temp = df_tag[[thread_col, tag_col]].copy()
    temp[tag_col] = temp[tag_col].map(_safe_text)
    tags = (
        temp.groupby(thread_col)[tag_col]
        .apply(lambda series: ";".join(sorted(set(filter(None, series.tolist())))))
        .reset_index()
    )
    return tags.rename(columns={thread_col: "thread_id", tag_col: "tags"})


def _extract_user_lang(df_user: Optional[pd.DataFrame], df_chat: pd.DataFrame, chat_id_col: str) -> pd.DataFrame:
    if df_user is None or df_user.empty or df_chat is None or df_chat.empty:
        return pd.DataFrame(columns=["thread_id", "user_lang"])

    chat_user_col = _find_col(df_chat, [r"(^userId$|user.?id)"])
    if not chat_user_col or chat_user_col not in df_chat.columns:
        return pd.DataFrame(columns=["thread_id", "user_lang"])

    user_id_col = _find_col(df_user, [r"(^id$|userId|^ID$)"])
    lang_col = _find_col(df_user, [r"(lang|language)"])
    if not user_id_col or not lang_col:
        return pd.DataFrame(columns=["thread_id", "user_lang"])

    chat_subset = df_chat[[chat_id_col, chat_user_col]].copy()
    chat_subset.columns = ["thread_id", "user_id"]
    user_subset = df_user[[user_id_col, lang_col]].copy()
    user_subset.columns = ["user_id", "user_lang"]

    merged = chat_subset.merge(user_subset, on="user_id", how="left")
    merged["user_lang"] = merged["user_lang"].map(_safe_text)
    return merged[["thread_id", "user_lang"]]


def _get_sheet(sheets: Mapping[str, pd.DataFrame], target: str) -> Optional[pd.DataFrame]:
    for name, df in sheets.items():
        if name.strip().lower() == target.lower():
            return df
    return None
