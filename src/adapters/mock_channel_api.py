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
        topic="refund",
        user_texts=[
            "상품이 파손된 상태로 도착했습니다. 환불 요청할게요.",
            "사진도 첨부했는데요, 바로 처리 부탁드려요.",
        ],
        manager_texts=[
            "불편을 드려 죄송합니다. 즉시 환불 절차를 도와드릴게요.",
            "회수 기사 방문 후 환불 완료까지 2~3일 정도 걸립니다.",
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
        topic="delivery",
        user_texts=[
            "배송 조회가 계속 준비중이라고 뜹니다.",
            "월요일 행사라 꼭 그 전에 받아야 해요.",
        ],
        manager_texts=[
            "택배사 시스템 오류로 조회가 늦었습니다.",
            "당일 발송으로 재지시했으니 내일 수령 가능합니다.",
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
    MockConversationTemplate(
        topic="payment",
        user_texts=[
            "결제를 했는데 영수증이 메일로 오지 않았어요.",
            "중복 청구가 된 것 같아요.",
        ],
        manager_texts=[
            "결제 내역을 확인 후 영수증을 재발송해드릴게요.",
            "중복 청구 건은 즉시 환불 처리하겠습니다.",
        ],
    ),
    MockConversationTemplate(
        topic="account",
        user_texts=[
            "비밀번호를 잊어버려서 로그인할 수 없습니다.",
            "인증 메일도 오질 않아요.",
        ],
        manager_texts=[
            "임시 비밀번호를 발급해 드릴게요.",
            "인증 메일이 스팸함에 있는지 확인 부탁드립니다.",
        ],
    ),
    MockConversationTemplate(
        topic="bug",
        user_texts=[
            "앱에서 결제 버튼을 누르면 계속 오류가 납니다.",
            "다른 기기에서도 동일해요.",
        ],
        manager_texts=[
            "기술팀에 전달해 패치 일정을 확인하겠습니다.",
            "임시로 웹 버전을 이용해 주시면 감사하겠습니다.",
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
