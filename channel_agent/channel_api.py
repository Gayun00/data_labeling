import logging
from typing import Any, Dict, Optional

from .config import ChannelTalkConfig

logger = logging.getLogger(__name__)


class ChannelTalkClient:
    """Thin HTTP client for ChannelTalk Open API (v5).

    현재 네트워크 호출이 어려워 요청 코드는 주석 처리했고,
    인터페이스에 맞춘 목 데이터(mock)를 반환합니다.
    실제 연동 시 주석을 해제하고 requests를 사용하세요.
    """

    def __init__(self, config: ChannelTalkConfig):
        config.validate()
        self.config = config

    def _headers(self) -> Dict[str, str]:
        return {
            "X-Access-Key": self.config.access_key,
            "X-Access-Secret": self.config.access_secret,
        }

    def fetch_user_chat_list(
        self, created_from: str, created_to: str, cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        logger.debug("Mock fetch chat list %s -> %s cursor=%s", created_from, created_to, cursor)
        # 실제 호출 예시
        # url = f"{self.config.base_url}/open/v5/user-chats"
        # params = {"createdFrom": created_from, "createdTo": created_to}
        # if cursor:
        #     params["cursor"] = cursor
        # res = requests.get(url, headers=self._headers(), params=params, timeout=30)
        # res.raise_for_status()
        # return res.json()

        # 목 데이터: 다양한 환불/배송/강사 문의/기능 제안
        mock_user_chats = [
            # 1) 수강 환불/불만 다양한 케이스
            {"id": "chat_001", "userId": "user_100", "name": "홍길동", "description": "배송 문의", "state": "open", "openedAt": "2024-08-01T09:00:00Z", "closedAt": None, "tags": ["배송", "일반문의"], "chatUrl": "https://open.channel.io/chats/chat_001"},
            {"id": "chat_002", "userId": "user_101", "name": "김영희", "description": "환불 요청", "state": "closed", "openedAt": "2024-08-02T11:00:00Z", "closedAt": "2024-08-02T12:00:00Z", "tags": ["환불", "결제"], "chatUrl": "https://open.channel.io/chats/chat_002"},
            {"id": "chat_003", "userId": "user_102", "name": "박민수", "description": "만족도 낮음, UI 불편", "state": "open", "openedAt": "2024-08-03T08:00:00Z", "closedAt": None, "tags": ["환불", "uiux"], "chatUrl": "https://open.channel.io/chats/chat_003"},
            {"id": "chat_004", "userId": "user_103", "name": "이지은", "description": "가격이 너무 비쌈", "state": "open", "openedAt": "2024-08-03T10:00:00Z", "closedAt": None, "tags": ["환불", "가격"], "chatUrl": "https://open.channel.io/chats/chat_004"},
            {"id": "chat_017", "userId": "user_116", "name": "최은지", "description": "배송이 지연됨", "state": "open", "openedAt": "2024-08-06T12:00:00Z", "closedAt": None, "tags": ["배송", "지연"], "chatUrl": "https://open.channel.io/chats/chat_017"},

            # 2) 도서 상품/배송/반품
            {"id": "chat_005", "userId": "user_104", "name": "최서연", "description": "도서 배송 확인", "state": "open", "openedAt": "2024-08-04T09:30:00Z", "closedAt": None, "tags": ["도서", "배송"], "chatUrl": "https://open.channel.io/chats/chat_005"},
            {"id": "chat_006", "userId": "user_105", "name": "윤정호", "description": "도서 반품 문의", "state": "open", "openedAt": "2024-08-04T10:00:00Z", "closedAt": None, "tags": ["도서", "반품"], "chatUrl": "https://open.channel.io/chats/chat_006"},
            {"id": "chat_007", "userId": "user_106", "name": "오하늘", "description": "배송 주소 변경", "state": "open", "openedAt": "2024-08-04T11:00:00Z", "closedAt": None, "tags": ["도서", "배송", "주소"], "chatUrl": "https://open.channel.io/chats/chat_007"},
            {"id": "chat_018", "userId": "user_117", "name": "이도연", "description": "책 반품 요청", "state": "open", "openedAt": "2024-08-06T13:00:00Z", "closedAt": None, "tags": ["도서", "반품"], "chatUrl": "https://open.channel.io/chats/chat_018"},

            # 3) 강사별 수강/환불 문의 (3명 x 2개 상품)
            {"id": "chat_008", "userId": "user_107", "name": "강도현", "description": "강사A 코스1 환불", "state": "open", "openedAt": "2024-08-05T09:00:00Z", "closedAt": None, "tags": ["강사A", "코스1", "환불"], "chatUrl": "https://open.channel.io/chats/chat_008"},
            {"id": "chat_009", "userId": "user_108", "name": "백승우", "description": "강사A 코스2 문의", "state": "open", "openedAt": "2024-08-05T09:30:00Z", "closedAt": None, "tags": ["강사A", "코스2", "수강문의"], "chatUrl": "https://open.channel.io/chats/chat_009"},
            {"id": "chat_010", "userId": "user_109", "name": "문하린", "description": "강사B 코스1 환불", "state": "open", "openedAt": "2024-08-05T10:00:00Z", "closedAt": None, "tags": ["강사B", "코스1", "환불"], "chatUrl": "https://open.channel.io/chats/chat_010"},
            {"id": "chat_011", "userId": "user_110", "name": "신유진", "description": "강사B 코스2 수강문의", "state": "open", "openedAt": "2024-08-05T10:30:00Z", "closedAt": None, "tags": ["강사B", "코스2", "수강문의"], "chatUrl": "https://open.channel.io/chats/chat_011"},
            {"id": "chat_012", "userId": "user_111", "name": "정호진", "description": "강사C 코스1 환불", "state": "open", "openedAt": "2024-08-05T11:00:00Z", "closedAt": None, "tags": ["강사C", "코스1", "환불"], "chatUrl": "https://open.channel.io/chats/chat_012"},
            {"id": "chat_013", "userId": "user_112", "name": "서윤아", "description": "강사C 코스2 문의", "state": "open", "openedAt": "2024-08-05T11:30:00Z", "closedAt": None, "tags": ["강사C", "코스2", "수강문의"], "chatUrl": "https://open.channel.io/chats/chat_013"},
            {"id": "chat_019", "userId": "user_118", "name": "장은호", "description": "강사A 코스1 만족도 낮음 환불 고민", "state": "open", "openedAt": "2024-08-06T14:00:00Z", "closedAt": None, "tags": ["강사A", "코스1", "환불"], "chatUrl": "https://open.channel.io/chats/chat_019"},

            # 4) 기능 제안
            {"id": "chat_014", "userId": "user_113", "name": "추가요청1", "description": "스크립트 제공 요청", "state": "open", "openedAt": "2024-08-06T08:00:00Z", "closedAt": None, "tags": ["제안", "스크립트"], "chatUrl": "https://open.channel.io/chats/chat_014"},
            {"id": "chat_015", "userId": "user_114", "name": "추가요청2", "description": "다크모드 필요", "state": "open", "openedAt": "2024-08-06T09:00:00Z", "closedAt": None, "tags": ["제안", "다크모드"], "chatUrl": "https://open.channel.io/chats/chat_015"},
            {"id": "chat_016", "userId": "user_115", "name": "추가요청3", "description": "모바일 최적화 제안", "state": "open", "openedAt": "2024-08-06T10:00:00Z", "closedAt": None, "tags": ["제안", "모바일"], "chatUrl": "https://open.channel.io/chats/chat_016"},
        ]
        return {
            "userChats": mock_user_chats,
            "nextCursor": None,
        }

    def fetch_chat_metadata(self, user_chat_id: str) -> Dict[str, Any]:
        logger.debug("Mock fetch chat metadata for %s", user_chat_id)
        # 실제 호출 예시
        # url = f"{self.config.base_url}/open/v5/user-chats/{user_chat_id}"
        # res = requests.get(url, headers=self._headers(), timeout=30)
        # res.raise_for_status()
        # return res.json()

        meta_map = {
            "chat_001": {"name": "홍길동", "description": "배송 문의", "tags": ["배송"]},
            "chat_002": {"name": "김영희", "description": "환불 요청", "tags": ["환불", "결제"]},
            "chat_003": {"name": "박민수", "description": "만족도 낮음, UI 불편", "tags": ["환불", "uiux"]},
            "chat_004": {"name": "이지은", "description": "가격 불만", "tags": ["환불", "가격"]},
            "chat_017": {"name": "최은지", "description": "배송 지연", "tags": ["배송", "지연"]},
            "chat_005": {"name": "최서연", "description": "도서 배송 확인", "tags": ["도서", "배송"]},
            "chat_006": {"name": "윤정호", "description": "도서 반품", "tags": ["도서", "반품"]},
            "chat_007": {"name": "오하늘", "description": "배송 주소 변경", "tags": ["도서", "배송", "주소"]},
            "chat_018": {"name": "이도연", "description": "책 반품 요청", "tags": ["도서", "반품"]},
            "chat_008": {"name": "강도현", "description": "강사A 코스1 환불", "tags": ["강사A", "코스1", "환불"]},
            "chat_009": {"name": "백승우", "description": "강사A 코스2 문의", "tags": ["강사A", "코스2", "수강문의"]},
            "chat_010": {"name": "문하린", "description": "강사B 코스1 환불", "tags": ["강사B", "코스1", "환불"]},
            "chat_011": {"name": "신유진", "description": "강사B 코스2 수강문의", "tags": ["강사B", "코스2", "수강문의"]},
            "chat_012": {"name": "정호진", "description": "강사C 코스1 환불", "tags": ["강사C", "코스1", "환불"]},
            "chat_013": {"name": "서윤아", "description": "강사C 코스2 문의", "tags": ["강사C", "코스2", "수강문의"]},
            "chat_019": {"name": "장은호", "description": "강사A 코스1 불만/환불 고민", "tags": ["강사A", "코스1", "환불"]},
            "chat_014": {"name": "추가요청1", "description": "스크립트 제공 요청", "tags": ["제안", "스크립트"]},
            "chat_015": {"name": "추가요청2", "description": "다크모드 필요", "tags": ["제안", "다크모드"]},
            "chat_016": {"name": "추가요청3", "description": "모바일 최적화", "tags": ["제안", "모바일"]},
        }
        base = meta_map.get(user_chat_id, {"name": "고객", "description": "문의", "tags": []})
        tag_objs = [{"id": f"tag_{i}", "name": t} for i, t in enumerate(base["tags"], start=1)]
        return {
            "id": user_chat_id,
            "userId": f"{user_chat_id}_user",
            "name": base["name"],
            "description": base["description"],
            "openedAt": "2024-08-01T09:00:00Z",
            "closedAt": None,
            "state": "open",
            "tags": tag_objs,
            "assignee": {"id": "agent_01", "name": "상담원A"},
            "chatUrl": f"https://open.channel.io/chats/{user_chat_id}",
        }

    def fetch_chat_messages(
        self, user_chat_id: str, limit: int = 100, cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        logger.debug("Mock fetch chat messages for %s cursor=%s", user_chat_id, cursor)
        # 실제 호출 예시
        # url = f"{self.config.base_url}/open/v5/user-chats/{user_chat_id}/messages"
        # params = {"limit": limit}
        # if cursor:
        #     params["cursor"] = cursor
        # res = requests.get(url, headers=self._headers(), params=params, timeout=30)
        # res.raise_for_status()
        # return res.json()

        messages_map = {
            "chat_001": [
                {"id": "m1", "personType": "customer", "plainText": "안녕하세요 배송이 언제 되나요? 010-1234-5678", "createdAt": "2024-08-01T09:01:00Z"},
                {"id": "m2", "personType": "manager", "plainText": "안녕하세요, 오늘 출고 예정입니다.", "createdAt": "2024-08-01T09:02:00Z"},
            ],
            "chat_002": [
                {"id": "m3", "personType": "customer", "plainText": "결제했는데 환불해주세요 계좌 123456789012", "createdAt": "2024-08-02T11:05:00Z"},
                {"id": "m4", "personType": "manager", "plainText": "확인 후 환불 도와드리겠습니다.", "createdAt": "2024-08-02T11:06:00Z"},
            ],
            "chat_003": [
                {"id": "m5", "personType": "customer", "plainText": "UI 너무 불편하고 로딩이 길어요. 환불 가능할까요? 010 2222 3333", "createdAt": "2024-08-03T08:10:00Z"},
                {"id": "m6", "personType": "manager", "plainText": "불편을 드려 죄송합니다. 환불 절차 안내드리겠습니다.", "createdAt": "2024-08-03T08:12:00Z"},
            ],
            "chat_004": [
                {"id": "m7", "personType": "customer", "plainText": "가격이 너무 비싸서 만족이 안 됩니다. 환불해주세요.", "createdAt": "2024-08-03T10:05:00Z"},
                {"id": "m8", "personType": "manager", "plainText": "프로모션 안내드릴까요, 아니면 바로 환불 도와드릴까요?", "createdAt": "2024-08-03T10:06:00Z"},
            ],
            "chat_005": [
                {"id": "m9", "personType": "customer", "plainText": "도서 배송 언제 도착하나요? 이름은 김책사요.", "createdAt": "2024-08-04T09:31:00Z"},
                {"id": "m10", "personType": "manager", "plainText": "금주 내 도착 예정입니다. 송장 보내드릴게요.", "createdAt": "2024-08-04T09:33:00Z"},
            ],
            "chat_006": [
                {"id": "m11", "personType": "customer", "plainText": "도서가 파손되어 반품하고 싶어요.", "createdAt": "2024-08-04T10:05:00Z"},
                {"id": "m12", "personType": "manager", "plainText": "불편을 드려 죄송합니다. 수거 접수해드리겠습니다.", "createdAt": "2024-08-04T10:06:00Z"},
            ],
            "chat_007": [
                {"id": "m13", "personType": "customer", "plainText": "배송 주소를 서울 강남구 테헤란로123 5층으로 바꿀 수 있나요?", "createdAt": "2024-08-04T11:05:00Z"},
                {"id": "m14", "personType": "manager", "plainText": "네 주소 변경 처리했습니다.", "createdAt": "2024-08-04T11:06:00Z"},
            ],
            "chat_008": [
                {"id": "m15", "personType": "customer", "plainText": "강사A 코스1 내용이 기대와 달라 환불하고 싶어요. 계좌는 987654321098", "createdAt": "2024-08-05T09:01:00Z"},
                {"id": "m16", "personType": "manager", "plainText": "확인 후 환불 진행하겠습니다.", "createdAt": "2024-08-05T09:02:00Z"},
            ],
            "chat_009": [
                {"id": "m17", "personType": "customer", "plainText": "강사A 코스2 수강하려고 하는데 난이도가 어떤가요?", "createdAt": "2024-08-05T09:31:00Z"},
                {"id": "m18", "personType": "manager", "plainText": "중급자 대상이며 예제 코드가 포함되어 있습니다.", "createdAt": "2024-08-05T09:32:00Z"},
            ],
            "chat_010": [
                {"id": "m19", "personType": "customer", "plainText": "강사B 코스1 환불 원합니다. 010-4444-5555로 연락주세요.", "createdAt": "2024-08-05T10:01:00Z"},
                {"id": "m20", "personType": "manager", "plainText": "전화 없이 바로 환불 처리해드릴까요?", "createdAt": "2024-08-05T10:02:00Z"},
            ],
            "chat_011": [
                {"id": "m21", "personType": "customer", "plainText": "강사B 코스2 라이브 세션 일정이 어떻게 되나요?", "createdAt": "2024-08-05T10:31:00Z"},
                {"id": "m22", "personType": "manager", "plainText": "매주 수요일 저녁 8시입니다.", "createdAt": "2024-08-05T10:32:00Z"},
            ],
            "chat_012": [
                {"id": "m23", "personType": "customer", "plainText": "강사C 코스1 환불하고 싶어요. 서울 마포구 거주합니다.", "createdAt": "2024-08-05T11:01:00Z"},
                {"id": "m24", "personType": "manager", "plainText": "확인 후 환불 도와드릴게요.", "createdAt": "2024-08-05T11:02:00Z"},
            ],
            "chat_013": [
                {"id": "m25", "personType": "customer", "plainText": "강사C 코스2에 자막 제공되나요?", "createdAt": "2024-08-05T11:31:00Z"},
                {"id": "m26", "personType": "manager", "plainText": "네, 자막과 스크립트가 제공됩니다.", "createdAt": "2024-08-05T11:32:00Z"},
            ],
            "chat_014": [
                {"id": "m27", "personType": "customer", "plainText": "강의 스크립트가 있으면 복습이 더 편할 것 같아요.", "createdAt": "2024-08-06T08:05:00Z"},
                {"id": "m28", "personType": "manager", "plainText": "좋은 제안 감사드립니다. 내부 검토하겠습니다.", "createdAt": "2024-08-06T08:06:00Z"},
            ],
            "chat_015": [
                {"id": "m29", "personType": "customer", "plainText": "다크모드가 꼭 필요해요. 눈이 아파요.", "createdAt": "2024-08-06T09:05:00Z"},
                {"id": "m30", "personType": "manager", "plainText": "피드백 감사합니다. 로드맵에 반영하겠습니다.", "createdAt": "2024-08-06T09:06:00Z"},
            ],
            "chat_016": [
                {"id": "m31", "personType": "customer", "plainText": "모바일에서 버튼이 너무 작아요. 개선 요청합니다.", "createdAt": "2024-08-06T10:05:00Z"},
                {"id": "m32", "personType": "manager", "plainText": "모바일 UI 개선 건으로 전달하겠습니다.", "createdAt": "2024-08-06T10:06:00Z"},
            ],
            "chat_017": [
                {"id": "m33", "personType": "customer", "plainText": "주문한 강의 교재가 계속 안 와요. 송장도 없고 시간 오래 걸리네요.", "createdAt": "2024-08-06T12:05:00Z"},
                {"id": "m34", "personType": "manager", "plainText": "지연 확인 후 송장/도착 예정일 안내드리겠습니다.", "createdAt": "2024-08-06T12:06:00Z"},
            ],
            "chat_018": [
                {"id": "m35", "personType": "customer", "plainText": "책이 생각보다 별로라 반품하고 싶습니다. 주소는 경기 용인시 기흥구 보정동이에요.", "createdAt": "2024-08-06T13:05:00Z"},
                {"id": "m36", "personType": "manager", "plainText": "수거 접수 도와드리겠습니다. 택배 기사 방문 일정 안내드릴게요.", "createdAt": "2024-08-06T13:06:00Z"},
            ],
            "chat_019": [
                {"id": "m37", "personType": "customer", "plainText": "강사A 코스1 내용이 기대 이하라서 환불할지 고민 중이에요. 010-7777-8888로 연락 주세요.", "createdAt": "2024-08-06T14:05:00Z"},
                {"id": "m38", "personType": "manager", "plainText": "불편 드려 죄송합니다. 환불 또는 다른 코스 추천 중 어떤 걸 도와드릴까요?", "createdAt": "2024-08-06T14:06:00Z"},
            ],
        }
        messages = messages_map.get(
            user_chat_id,
            [{"id": "m0", "personType": "customer", "plainText": "안녕하세요", "createdAt": "2024-08-01T00:00:00Z"}],
        )
        return {"messages": messages, "nextCursor": None}

    def fetch_tags(self) -> Dict[str, Any]:
        logger.debug("Mock fetch tags")
        return {
            "tags": [
                {"id": "tag_ship", "name": "배송"},
                {"id": "tag_refund", "name": "환불"},
                {"id": "tag_bug", "name": "버그"},
            ]
        }
