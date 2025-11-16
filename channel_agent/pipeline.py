import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .agent import ChannelAgent
from .channel_api import ChannelTalkClient
from .config import PipelineConfig
from .pii import mask_pii
from .storage import LabeledChat, save_results_csv

logger = logging.getLogger(__name__)


@dataclass
class ChatBundle:
    user_chat_id: str
    metadata: Dict[str, Any]
    messages: List[Dict[str, Any]]


class ChannelLabelingPipeline:
    """End-to-end pipeline: fetch -> mask -> label -> persist."""

    def __init__(
        self,
        channel_client: ChannelTalkClient,
        agent: ChannelAgent,
        config: Optional[PipelineConfig] = None,
    ):
        self.channel_client = channel_client
        self.agent = agent
        self.config = config or PipelineConfig()

    def _collect_messages(self, chat_id: str) -> List[Dict[str, Any]]:
        cursor: Optional[str] = None
        messages: List[Dict[str, Any]] = []
        while True:
            payload = self.channel_client.fetch_chat_messages(
                chat_id, limit=self.config.message_page_size, cursor=cursor
            )
            chunk = payload.get("messages", [])
            messages.extend(chunk)
            cursor = payload.get("nextCursor") or payload.get("next") or payload.get("cursor")
            has_more = (
                payload.get("hasMore")
                or payload.get("has_next")
                or bool(cursor)
            )
            if not has_more or not chunk:
                break
        logger.debug("Fetched %d messages for %s", len(messages), chat_id)
        return messages

    def _fetch_chat_bundle(self, user_chat_id: str) -> ChatBundle:
        metadata = self.channel_client.fetch_chat_metadata(user_chat_id)
        messages = self._collect_messages(user_chat_id)
        return ChatBundle(user_chat_id=user_chat_id, metadata=metadata, messages=messages)

    def _merge_dialog_text(self, messages: List[Dict[str, Any]]) -> str:
        def message_key(msg: Dict[str, Any]) -> Any:
            return msg.get("createdAt") or msg.get("created_at") or msg.get("id")

        ordered = sorted(messages, key=message_key)
        merged: List[str] = []
        for msg in ordered:
            sender_info = msg.get("sender") or msg.get("author") or {}
            sender_name = sender_info.get("name") or sender_info.get("id") or msg.get("senderName")
            if not sender_name:
                person_type = msg.get("personType")
                if person_type == "customer":
                    sender_name = "customer"
                elif person_type == "manager":
                    sender_name = "manager"
                else:
                    sender_name = "unknown"
            text = mask_pii(msg.get("plainText") or msg.get("message") or "")
            merged.append(f"[{sender_name}] {text}")
        return "\n".join(merged)

    def run(self, created_from: str, created_to: str) -> str:
        """Run the pipeline for a date range and return the output CSV path."""
        chat_ids = self._paginate_chat_ids(created_from, created_to)
        logger.info("Collected %d chats between %s and %s", len(chat_ids), created_from, created_to)

        labeled_rows: List[LabeledChat] = []
        for chat_id in chat_ids:
            bundle = self._fetch_chat_bundle(chat_id)
            dialog_text = self._merge_dialog_text(bundle.messages)
            result = self.agent.summarize_and_label_dialog(dialog_text)
            labeled_rows.append(
                LabeledChat(
                    user_chat_id=chat_id,
                    summary=result.get("summary", ""),
                    labels=result.get("labels", []),
                    emotion=result.get("emotion"),
                    created_at=bundle.metadata.get("createdAt") if isinstance(bundle.metadata, dict) else None,
                    custom_fields=bundle.metadata,
                )
            )

        output_path = save_results_csv(
            self.config.output_dir, self.config.output_file, labeled_rows
        )
        logger.info("Saved %d labeled chats to %s", len(labeled_rows), output_path)
        return output_path

    def _paginate_chat_ids(self, created_from: str, created_to: str) -> List[str]:
        cursor: Optional[str] = None
        ids: List[str] = []
        while True:
            payload = self.channel_client.fetch_user_chat_list(
                created_from, created_to, cursor=cursor
            )
            chats = payload.get("userChats") or payload.get("chats") or payload.get("data") or []
            for chat in chats:
                chat_id = chat.get("id") or chat.get("userChatId") or chat.get("user_chat_id")
                if chat_id:
                    ids.append(chat_id)
            cursor = payload.get("nextCursor") or payload.get("next") or payload.get("cursor")
            has_more = payload.get("hasMore") or bool(cursor)
            if not has_more:
                break
        return ids
