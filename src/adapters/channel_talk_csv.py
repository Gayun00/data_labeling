"""Adapter to normalize ChannelTalk exports into Conversation objects."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Optional

import pandas as pd

from src.models.conversation import (
    BotProfile,
    Conversation,
    ManagerProfile,
    Message,
    Participants,
    UserProfile,
)


@dataclass
class ChannelTalkCSVAdapter:
    """Normalizes ChannelTalk CSV/Excel exports into Conversation objects."""

    dataframes: Dict[str, pd.DataFrame]

    def conversations(self) -> Iterable[Conversation]:
        userchat_df = self._get_dataframe("UserChat")
        message_df = self._get_dataframe("Message")

        users = self._prepare_users()
        managers = self._prepare_managers()
        bots = self._prepare_bots()
        workflows = self._prepare_workflows()
        tags = self._prepare_tags()

        messages_grouped = self._group_messages(message_df)

        for _, row in userchat_df.iterrows():
            conv_id = str(row["id"])

            convo_messages = messages_grouped.get(conv_id, [])
            participant_user = users.get(str(row.get("userId")))
            participant_managers = [managers[mid] for mid in self._split_ids(row.get("managerIds"), "|") if mid in managers]

            participant_bots = []
            bot_ids = self._split_ids(row.get("botIds"))
            if bot_ids:
                participant_bots = [bots[bid] for bid in bot_ids if bid in bots]

            meta = {
                "state": row.get("state"),
                "priority": row.get("priority"),
                "workflow": workflows.get(str(row.get("workflowId"))),
                "tags": [tags[tag] for tag in self._split_ids(row.get("tags"), ",") if tag in tags],
                "goalState": row.get("goalState"),
                "csat": row.get("profile.csat"),
                "csatComment": row.get("profile.csatComment"),
                "url": row.get("url"),
            }

            conversation = Conversation(
                id=conv_id,
                channel_id=str(row.get("channelId")) if row.get("channelId") else None,
                created_at=self._parse_datetime(row.get("createdAt")) or datetime.utcnow(),
                closed_at=self._parse_datetime(row.get("closedAt")),
                participants=Participants(
                    user=participant_user,
                    managers=participant_managers,
                    bots=participant_bots,
                    meta={},
                ),
                messages=convo_messages,
                meta={key: value for key, value in meta.items() if value not in (None, [], {})},
            )

            yield conversation

    def _group_messages(self, message_df: pd.DataFrame) -> Dict[str, List[Message]]:
        grouped: Dict[str, List[Message]] = {}
        if message_df.empty:
            return grouped

        for _, row in message_df.iterrows():
            chat_id = str(row.get("chatId"))
            message = Message(
                id=str(row.get("messageId", row.get("id", ""))),
                conversation_id=chat_id,
                sender_type=str(row.get("personType", "system")).lower(),
                sender_id=str(row.get("personId")) if row.get("personId") else None,
                created_at=self._parse_datetime(row.get("createdAt")) or datetime.utcnow(),
                text=str(row.get("plainText", "")),
            )
            grouped.setdefault(chat_id, []).append(message)

        for chat_id in grouped:
            grouped[chat_id].sort(key=lambda msg: msg.created_at)
        return grouped

    def _prepare_users(self) -> Dict[str, UserProfile]:
        df = self._get_dataframe("User")
        if df.empty:
            return {}

        users: Dict[str, UserProfile] = {}
        for _, row in df.iterrows():
            user_id = str(row["id"])
            users[user_id] = UserProfile(
                id=user_id,
                name=row.get("profile.name"),
                email=row.get("profile.email"),
                phone=row.get("mobileNumber"),
                city=row.get("city"),
                country=row.get("country"),
                meta={
                    "member": row.get("member"),
                    "hasChat": row.get("hasChat"),
                },
            )
        return users

    def _prepare_managers(self) -> Dict[str, ManagerProfile]:
        df = self._get_dataframe("Manager")
        managers: Dict[str, ManagerProfile] = {}
        if df.empty:
            return managers

        for _, row in df.iterrows():
            manager_id = str(row.get("id"))
            managers[manager_id] = ManagerProfile(
                id=manager_id,
                name=row.get("name"),
                email=row.get("email"),
                meta={},
            )
        return managers

    def _prepare_bots(self) -> Dict[str, BotProfile]:
        df = self._get_dataframe("Bot")
        bots: Dict[str, BotProfile] = {}
        if df.empty:
            return bots
        for _, row in df.iterrows():
            bot_id = str(row.get("id"))
            bots[bot_id] = BotProfile(
                id=bot_id,
                name=row.get("name"),
                meta={"color": row.get("color")},
            )
        return bots

    def _prepare_workflows(self) -> Dict[str, Dict[str, str]]:
        df = self._get_dataframe("Workflow")
        workflows: Dict[str, Dict[str, str]] = {}
        if df.empty:
            return workflows
        for _, row in df.iterrows():
            workflow_id = str(row.get("id"))
            workflows[workflow_id] = {
                "revisionId": row.get("revisionId"),
                "sectionPath": row.get("sectionPath"),
                "causeOfEnd": row.get("causeOfEnd"),
            }
        return workflows

    def _prepare_tags(self) -> Dict[str, str]:
        df = self._get_dataframe("UserChatTag")
        tags: Dict[str, str] = {}
        if df.empty:
            return tags
        for _, row in df.iterrows():
            tag_name = str(row.get("name"))
            tags[tag_name] = tag_name
        return tags

    def _get_dataframe(self, name: str) -> pd.DataFrame:
        for key, df in self.dataframes.items():
            if key.lower() == name.lower():
                return df
        return pd.DataFrame()

    def _split_ids(self, value: Optional[object], separator: str = ",") -> List[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(separator) if item.strip()]
        return [str(value)]

    @staticmethod
    def _parse_datetime(value: Optional[object]) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        try:
            parsed = pd.to_datetime(value, errors="raise")
        except (ValueError, TypeError):
            return None
        if isinstance(parsed, pd.Series):
            parsed = parsed.iloc[0]
        if hasattr(parsed, "to_pydatetime"):
            parsed = parsed.to_pydatetime()
        if isinstance(parsed, (list, tuple)):
            parsed = parsed[0]
        if isinstance(parsed, datetime):
            return parsed
        return None
