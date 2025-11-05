from datetime import datetime

from src.models.sample import SampleLibrary, SampleRecord


def test_sample_library_serialization_roundtrip() -> None:
    record = SampleRecord(
        sample_id="sample-1",
        label_primary="inquiry",
        summary_for_embedding="문의 요약",
        label_secondary=["billing"],
        origin="ui_upload",
        created_at=datetime.utcnow(),
        meta={"channel": "email"},
    )
    library = SampleLibrary.from_records([record], origin="ui_upload")

    payload = library.to_dict()
    restored = SampleLibrary.from_dict(payload)

    assert len(restored) == 1
    restored_record = restored.get("sample-1")
    assert restored_record is not None
    assert restored_record.label_secondary == ["billing"]
    assert restored_record.meta["channel"] == "email"


def test_sample_library_merge_overwrites_by_id() -> None:
    first = SampleRecord(
        sample_id="sample-1",
        label_primary="inquiry",
        summary_for_embedding="문의 요약1",
        origin="first",
    )
    updated = SampleRecord(
        sample_id="sample-1",
        label_primary="complaint",
        summary_for_embedding="업데이트된 요약",
        origin="second",
    )

    base_library = SampleLibrary.from_records([first], origin="first")
    new_library = SampleLibrary.from_records([updated], origin="second")

    merged = base_library.merge(new_library)
    record = merged.get("sample-1")

    assert record is not None
    assert record.label_primary == "complaint"
    assert merged.origin == "merged"
