import re


# Precompile patterns for performance.
# 전화번호: 010-1234-5678 / 01012345678 등 (문장부호 앞뒤 허용)
_PHONE_PATTERN = re.compile(r"(01[016789])[ -]?(\d{3,4})[ -]?(\d{4})")
_PHONE_COMPACT_PATTERN = re.compile(r"01[016789]\d{7,8}")

# 계좌번호 등: 8~14자리 숫자
_ACCOUNT_PATTERN = re.compile(r"\b\d{8,14}\b")

# 주소 키워드: 광역시/도 + 주요 구
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
    # 주요 구/동 (서울 위주)
    "강남구",
    "서초구",
    "송파구",
    "마포구",
    "용산구",
    "종로구",
    "중구",
    "성동구",
    "영등포구",
    "동작구",
    "구로구",
    "노원구",
    "기흥구",
]

# 도로명/길 패턴: OO로123, OO길45 등
_ROAD_PATTERN = re.compile(r"[가-힣]{2,}(로|길)\s*\d+")

# 시/군 + 구/동 패턴: 용인시 기흥구 보정동
_CITY_GU_DONG_PATTERN = re.compile(r"[가-힣]{2,}(시|군)\s?[가-힣]{1,}구\s?[가-힣0-9]{1,}동")
# 구 + 동만 있는 경우: 강남구 테헤란로123 5층, 기흥구 보정동
_GU_DONG_ONLY_PATTERN = re.compile(r"[가-힣]{2,}구\s?[가-힣0-9]{1,}동")


def mask_pii(text: str) -> str:
    """
    Mask common PII types in Korean support chats:
    - Phone numbers (e.g., 010-1234-5678 -> ***-****-****)
    - Bank account numbers (8~14 digits)
    - Simple address hints (region/구/도로명)
    """

    if not text:
        return ""

    masked = _PHONE_PATTERN.sub("***-****-****", text)
    masked = _PHONE_COMPACT_PATTERN.sub("***-****-****", masked)
    masked = _ACCOUNT_PATTERN.sub("************", masked)

    # 주소 패턴을 먼저 처리
    masked = _CITY_GU_DONG_PATTERN.sub("***", masked)
    masked = _GU_DONG_ONLY_PATTERN.sub("***", masked)
    masked = _ROAD_PATTERN.sub("***", masked)
    for kw in _REGION_KEYWORDS:
        masked = re.sub(rf"{kw}[^\s,\.]*", "***", masked)
    return masked
