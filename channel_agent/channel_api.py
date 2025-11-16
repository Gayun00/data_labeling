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

        mock_user_chats = [
            {
                "id": "chat_001",
                "userId": "user_100",
                "name": "홍길동",
                "description": "배송 문의",
                "state": "open",
                "openedAt": "2024-08-01T09:00:00Z",
                "closedAt": None,
                "tags": ["배송", "일반문의"],
                "chatUrl": "https://open.channel.io/chats/chat_001",
            },
            {
                "id": "chat_002",
                "userId": "user_101",
                "name": "김영희",
                "description": "환불 요청",
                "state": "closed",
                "openedAt": "2024-08-02T11:00:00Z",
                "closedAt": "2024-08-02T12:00:00Z",
                "tags": ["환불", "결제"],
                "chatUrl": "https://open.channel.io/chats/chat_002",
            },
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

        return {
            "id": user_chat_id,
            "userId": f"{user_chat_id}_user",
            "name": "홍길동" if user_chat_id == "chat_001" else "김영희",
            "description": "배송 문의" if user_chat_id == "chat_001" else "환불 요청",
            "openedAt": "2024-08-01T09:00:00Z",
            "closedAt": None,
            "state": "open",
            "tags": [{"id": "tag_ship", "name": "배송"}],
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

        if user_chat_id == "chat_001":
            messages = [
                {
                    "id": "m1",
                    "personType": "customer",
                    "plainText": "안녕하세요 배송이 언제 되나요? 010-1234-5678",
                    "createdAt": "2024-08-01T09:01:00Z",
                },
                {
                    "id": "m2",
                    "personType": "manager",
                    "plainText": "안녕하세요, 오늘 출고 예정입니다.",
                    "createdAt": "2024-08-01T09:02:00Z",
                },
            ]
        else:
            messages = [
                {
                    "id": "m3",
                    "personType": "customer",
                    "plainText": "결제했는데 환불해주세요 계좌 123456789012",
                    "createdAt": "2024-08-02T11:05:00Z",
                },
                {
                    "id": "m4",
                    "personType": "manager",
                    "plainText": "확인 후 환불 도와드리겠습니다.",
                    "createdAt": "2024-08-02T11:06:00Z",
                },
            ]
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
