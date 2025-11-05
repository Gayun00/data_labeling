from datetime import datetime

from src.models.conversation import Conversation, Message, Participants
from src.models.sample import SampleLibrary, SampleRecord
from src.retrieval import SimilarityRetriever


def make_conversation(text: str) -> Conversation:
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


def test_similarity_retriever_returns_top_match() -> None:
    records = SampleLibrary.from_records(
        [
            SampleRecord(sample_id="s1", label_primary="billing", summary_for_embedding="결제 오류 문의"),
            SampleRecord(sample_id="s2", label_primary="bug", summary_for_embedding="앱이 자꾸 종료된다"),
        ],
        origin="test",
    )

    retriever = SimilarityRetriever(top_k=1)
    convo = make_conversation("결제가 되지 않는 것 같아요")

    matches = retriever.retrieve(convo, records)

    assert len(matches) == 1
    assert matches[0].sample_id == "s1"
