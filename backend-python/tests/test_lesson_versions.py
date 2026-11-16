import copy

from cuoti_backend.lessons import compact, digest, source_version, version_matches


def test_lesson_versions_preserve_material_not_import_metadata():
    cards = [
        {
            "id": "old",
            "code": "eq",
            "name": "等式",
            "subject": "数学",
            "content": {"grade": "初一", "formula": "a=b"},
            "created_at": "old",
        }
    ]
    newer = copy.deepcopy(cards)
    newer[0].update(id="new", created_at="new")
    assert source_version(newer) == source_version(cards)
    assert version_matches(
        {"input_fingerprint": digest(compact(cards)) + ":" + digest("问题")},
        cards,
        "问题",
    )
    newer[0]["content"]["formula"] = "a>b"
    assert source_version(newer) != source_version(cards)
    assert not version_matches(
        {"input_fingerprint": source_version(cards) + ":" + digest("问题")},
        newer,
        "问题",
    )
    newer = copy.deepcopy(cards)
    newer[0]["retrieval_role"] = "prerequisite"
    assert source_version(newer) != source_version(cards)
