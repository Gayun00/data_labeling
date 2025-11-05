from datetime import datetime

import pandas as pd

from src.adapters.channel_talk_csv import ChannelTalkCSVAdapter


def make_sample_dataframes() -> dict:
    userchat = pd.DataFrame(
        [
            {
                "id": "chat-1",
                "userId": "user-1",
                "managerIds": "mgr-1",
                "state": "closed",
                "createdAt": "2024-07-01T10:00:00",
                "closedAt": "2024-07-01T11:00:00",
                "tags": "billing",
            }
        ]
    )
    message = pd.DataFrame(
        [
            {
                "chatId": "chat-1",
                "messageId": "msg-1",
                "personType": "user",
                "personId": "user-1",
                "plainText": "안녕하세요.",
                "createdAt": "2024-07-01T10:05:00",
            },
            {
                "chatId": "chat-1",
                "messageId": "msg-2",
                "personType": "manager",
                "personId": "mgr-1",
                "plainText": "무엇을 도와드릴까요?",
                "createdAt": "2024-07-01T10:06:00",
            },
        ]
    )
    user = pd.DataFrame(
        [
            {
                "id": "user-1",
                "profile.name": "홍길동",
                "profile.email": "hong@example.com",
            }
        ]
    )
    manager = pd.DataFrame(
        [
            {"id": "mgr-1", "name": "관리자A", "email": "manager@example.com"},
        ]
    )
    tags = pd.DataFrame(
        [
            {"name": "billing"},
        ]
    )

    return {
        "UserChat": userchat,
        "Message": message,
        "User": user,
        "Manager": manager,
        "UserChatTag": tags,
    }


def test_adapter_creates_conversation() -> None:
    adapter = ChannelTalkCSVAdapter(dataframes=make_sample_dataframes())
    conversations = list(adapter.conversations())

    assert len(conversations) == 1
    convo = conversations[0]
    assert convo.id == "chat-1"
    assert convo.participants.user is not None
    assert len(convo.participants.managers) == 1
    assert len(convo.messages) == 2
    assert convo.messages[0].text == "안녕하세요."
    assert convo.meta["tags"] == ["billing"]
