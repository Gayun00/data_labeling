from datetime import datetime

from src.models.conversation import Conversation, Message, Participants
from src.models.sample import SampleLibrary, SampleRecord
from src.pipeline import LabelingPipeline
from src.retrieval import SimilarityRetriever


def build_conversation(text: str) -> Conversation:
    message = Message(
        id="msg-1",
        conversation_id="chat-1",
        sender_type="user",
        sender_id="user-1",
        created_at=datetime.utcnow(),
        text=text,
    )
    return Conversation(
        id="chat-1",
        channel_id=None,
        created_at=datetime.utcnow(),
        closed_at=None,
        participants=Participants(user=None),
        messages=[message],
        meta={},
    )


def test_labeling_pipeline_fallback() -> None:
    library = SampleLibrary.from_records(
        [
            SampleRecord(sample_id="s1", label_primary="billing", summary_for_embedding="결제 관련 문의"),
            SampleRecord(sample_id="s2", label_primary="bug", summary_for_embedding="앱이 종료됨"),
        ],
        origin="test",
    )

    pipeline = LabelingPipeline(SimilarityRetriever(top_k=2), llm_service=None)
    result = pipeline.run([build_conversation("결제 오류가 발생합니다")], library)

    assert len(result.records) == 1
    assert result.records[0].result.label_primary == "billing"
