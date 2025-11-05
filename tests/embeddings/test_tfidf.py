from src.embeddings import TfidfEmbedder


def test_tfidf_embedder_returns_vectors() -> None:
    embedder = TfidfEmbedder(max_features=16)
    texts = ["안녕하세요 고객센터입니다.", "결제 관련 문의드립니다."]

    embeddings = embedder.embed(texts)

    assert len(embeddings) == len(texts)
    assert all(len(vec) <= 16 for vec in embeddings)
