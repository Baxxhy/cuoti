from cuoti_backend.learning_memory import audit_manifest, entry, sorted_json


def test_memory_entry_bounds_source_and_classification():
    row = {"id": "sample", "updated_at": "2026-11-17T00:00:00+00:00", "score": 1.0}
    item = entry("mastery", row, "", "estimate", "历史估计", 30, "", ["mastery:sample"])
    assert item["expires_at"] - item["observed_at"] == 30 * 86400
    assert item["outcome"] == "unknown" and item["independence"] == "not_applicable"
    assert audit_manifest({"entries": [item]})[0]["ref"] == "mastery:sample"
    assert sorted_json({"b": 1.0, "a": True}) == '{"a": true, "b": 1}'
