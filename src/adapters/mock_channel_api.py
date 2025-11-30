"""Mock ChannelTalk API responses for local demos."""

from __future__ import annotations

import random
import string
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class MockConversationTemplate:
    topic: str
    user_texts: List[str]
    manager_texts: List[str]


TEMPLATES: List[MockConversationTemplate] = [
    MockConversationTemplate(
        topic="refund",
        user_texts=[
            "신발이 마음에 들지 않아 환불하고 싶어요.",
            "주문번호는 O-12345입니다.",
        ],
        manager_texts=[
            "환불 진행을 위해 주문 정보를 확인하겠습니다.",
            "택배 회수 후 3영업일 내 환불 예정입니다.",
        ],
    ),
    MockConversationTemplate(
        topic="delivery",
        user_texts=[
            "배송이 너무 늦어요.",
            "이번 주 안에 받아야 하는데 가능할까요?",
        ],
        manager_texts=[
            "물류 지연으로 하루 정도 늦춰졌습니다.",
            "내일 도착하도록 택배사에 재요청했습니다.",
        ],
    ),
    MockConversationTemplate(
        topic="product",
        user_texts=[
            "노트북이 갑자기 꺼져버립니다.",
            "전원 케이블을 바꿔도 동일합니다.",
        ],
        manager_texts=[
            "수리를 위해 회수 접수를 도와드리겠습니다.",
            "주소 확인 후 2일 내 기사님 방문 예정입니다.",
        ],
    ),
]


class MockChannelTalkAPI:
    """Create pseudo ChannelTalk API payloads for demos."""

    channel_id: str = "ch_demo"

    def fetch_user_chats(self, count: int = 3) -> Tuple[dict, Dict[str, dict]]:
        now = datetime.utcnow()
        user_chats: List[dict] = []
        messages_payloads: Dict[str, dict] = {}

        for idx in range(count):
            template = random.choice(TEMPLATES)
            chat_id = self._make_chat_id(now, idx)
            created_at = int((now - timedelta(minutes=idx * 3)).timestamp())

            user_chats.append(
                {
                    "id": chat_id,
                    "channelId": self.channel_id,
                    "state": "opened",
                    "managed": True,
                    "userId": f"user_{chat_id}",
                    "tags": [template.topic],
                    "createdAt": created_at,
                    "openedAt": created_at + 5,
                    "closedAt": None,
                }
            )

            messages_payloads[chat_id] = {
                "messages": self._build_messages(chat_id, template, created_at)
            }

        payload = {"next": None, "userChats": user_chats}
        return payload, messages_payloads

    def _build_messages(self, chat_id: str, template: MockConversationTemplate, base_ts: int) -> List[dict]:
        messages: List[dict] = []
        ts = base_ts
        counter = 0
        for idx, text in enumerate(template.user_texts):
            counter += 1
            ts += 60
            messages.append(
                {
                    "id": f"msg_{chat_id}_{counter}",
                    "chatId": chat_id,
                    "personType": "user",
                    "personId": f"user_{chat_id}",
                    "plainText": text,
                    "createdAt": ts,
                    "state": "sent",
                }
            )
            if idx < len(template.manager_texts):
                counter += 1
                ts += 60
                messages.append(
                    {
                        "id": f"msg_{chat_id}_{counter}",
                        "chatId": chat_id,
                        "personType": "manager",
                        "personId": "mgr_mock",
                        "plainText": template.manager_texts[idx],
                        "createdAt": ts,
                        "state": "sent",
                    }
                )
        return messages

    def _make_chat_id(self, ts: datetime, idx: int) -> str:
        suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
        return f"mock_{ts.strftime('%Y%m%d%H%M%S')}_{idx}_{suffix}"
