import re


# Precompile patterns for performance.
_PHONE_PATTERN = re.compile(r"\b(01[0-9])[ -]?(\d{3,4})[ -]?(\d{4})\b")
_ACCOUNT_PATTERN = re.compile(r"\b\d{8,14}\b")
_REGION_KEYWORDS = [
    "서울",
    "경기",
    "부산",
    "대구",
    "인천",
    "광주",
    "대전",
    "울산",
    "세종",
    "제주",
]


def mask_pii(text: str) -> str:
    """
    Mask common PII types in Korean support chats:
    - Phone numbers (e.g., 010-1234-5678 -> ***-****-****)
    - Bank account numbers (8~14 digits)
    - Simple address hints (region keywords followed by non-space chars)
    """

    if not text:
        return ""

    masked = _PHONE_PATTERN.sub("***-****-****", text)
    masked = _ACCOUNT_PATTERN.sub("************", masked)
    for kw in _REGION_KEYWORDS:
        masked = re.sub(rf"{kw}[^\s,\.]*", "***", masked)
    return masked

