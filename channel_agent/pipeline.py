import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .agent import ChannelAgent
from .channel_api import ChannelTalkClient
from .config import PipelineConfig
from .pii import mask_pii, count_profanity
from .storage import (
    LabeledChat,
    SkippedChat,
    FlatLabel,
    save_results_csv,
    save_skipped_csv,
    save_flat_labels_csv,
)
from .sample_vectors import search_sample_index

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
            raw_text = msg.get("plainText") or msg.get("message") or ""
            text = raw_text if self.config.disable_local_mask else mask_pii(raw_text)
            merged.append(f"[{sender_name}] {text}")
        return "\n".join(merged)

    def _is_off_topic(self, dialog_text: str) -> bool:
        """Return True if dialog is abusive/off-topic (no service keywords but high profanity)."""
        profanity_count = count_profanity(dialog_text)
        has_service_kw = any(kw in dialog_text for kw in self.config.service_keywords)
        return profanity_count >= self.config.abuse_threshold and not has_service_kw

    def run(self, created_from: str, created_to: str) -> str:
        """Run the pipeline for a date range and return the output CSV path."""
        chat_ids = self._paginate_chat_ids(created_from, created_to)
        logger.info("Collected %d chats between %s and %s", len(chat_ids), created_from, created_to)

        labeled_rows: List[LabeledChat] = []
        skipped_rows: List[SkippedChat] = []
        flat_labels: List[FlatLabel] = []
        for chat_id in chat_ids:
            bundle = self._fetch_chat_bundle(chat_id)
            dialog_text = self._merge_dialog_text(bundle.messages)
            if self._is_off_topic(dialog_text):
                logger.info("Skipping off-topic/abusive chat_id=%s", chat_id)
                skipped_rows.append(SkippedChat(user_chat_id=chat_id, reason="off_topic/abuse", dialog=dialog_text))
                continue
            sample_prompt, sample_labels = (
                self._build_prompt_with_samples(dialog_text) if self.config.use_sample_index else (dialog_text, [])
            )
            result = self.agent.summarize_and_label_dialog(sample_prompt)

            # 샘플 라벨이 있으면 그걸 우선(가이드라인)으로 사용, 없으면 에이전트 라벨 사용
            merged_labels = list(dict.fromkeys(sample_labels or (result.get("labels") or [])))
            # 라벨은 최대 2개까지만 허용
            merged_labels = merged_labels[:2]
            for lbl in merged_labels:
                flat_labels.append(FlatLabel(user_chat_id=chat_id, label=lbl))

            # 요약이 프롬프트 안내문을 그대로 담았을 경우 원본 대화 요약으로 대체
            summary_text = result.get("summary", "")
            if ("아래 샘플 라벨" in summary_text) or ("[분석 대상 대화]" in summary_text):
                summary_text = (dialog_text[:200] + "...") if len(dialog_text) > 200 else dialog_text
            if not summary_text:
                summary_text = (dialog_text[:200] + "...") if len(dialog_text) > 200 else dialog_text
            # LLM 출력에도 PII/비속어 마스킹 적용해 2차 보호
            summary_text = mask_pii(summary_text)

            labeled_rows.append(
                LabeledChat(
                    user_chat_id=chat_id,
                    summary=summary_text,
                    labels=merged_labels,
                    emotion=result.get("emotion"),
                    created_at=bundle.metadata.get("createdAt") if isinstance(bundle.metadata, dict) else None,
                    custom_fields=bundle.metadata,
                )
            )

        output_path = save_results_csv(
            self.config.output_dir, self.config.output_file, labeled_rows
        )
        logger.info("Saved %d labeled chats to %s", len(labeled_rows), output_path)
        if skipped_rows:
            skipped_path = save_skipped_csv(
                self.config.output_dir, self.config.skipped_output_file, skipped_rows
            )
            logger.info("Skipped %d chats to %s", len(skipped_rows), skipped_path)
        else:
            skipped_path = None
        if flat_labels:
            labels_path = save_flat_labels_csv(
                self.config.output_dir,
                "chat_labels.csv",
                flat_labels,
            )
            logger.info("Saved flat labels to %s", labels_path)
        return output_path

    def _build_prompt_with_samples(self, dialog_text: str) -> (str, List[str]):
        """Attach few-shot examples; return (prompt, sample_labels)."""
        try:
            results = search_sample_index(
                dialog_text,
                top_k=self.config.sample_top_k,
                use_mock_embeddings=self.config.sample_use_mock_embeddings,
                model=self.config.sample_embed_model,
            )
        except Exception as exc:  # index missing or embed failure
            logger.warning("Sample index unavailable or search failed: %s", exc)
            return dialog_text, []

        if not results:
            return dialog_text, []

        examples: List[str] = []
        # 샘플 라벨은 Top-1만 사용하여 과다 라벨 부착 방지
        top_labels: List[str] = results[0][0].labels or []
        for idx, (rec, score) in enumerate(results, start=1):
            label_str = "|".join(rec.labels) if rec.labels else "없음"
            examples.append(
                f"[샘플 {idx}] 유사도:{score:.2f}\n텍스트: {rec.text}\n라벨: {label_str}"
            )

        few_shot_block = "\n\n".join(examples)
        guidance = (
            "- 아래 샘플 라벨을 가능한 한 재사용하세요 (최대 2개).\n"
            "- 샘플에 등장한 라벨 이름(예: 강사A, 코스1, 환불 등)을 우선 고려하세요.\n"
            "- 대화와 무관한 라벨은 넣지 말고, 새 라벨을 추가해도 총 2개를 넘기지 마세요."
        )
        return (
            f"{guidance}\n\n"
            f"{few_shot_block}\n\n"
            "[분석 대상 대화]\n"
            f"{dialog_text}"
        ), list(dict.fromkeys(top_labels))

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
