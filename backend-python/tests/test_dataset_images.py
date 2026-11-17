from types import SimpleNamespace

from cuoti_backend.dataset_images import layout, question_images, solution_images
from cuoti_backend.practice_context import fingerprint_json


def test_picture_indices_never_mix_question_and_answer():
    question = {
        "id": "q",
        "question_text": "题目<ImageHere>",
        "options": ["A<ImageHere>", "B"],
        "answer": "<ImageHere>",
        "solution": "解答<ImageHere>",
        "image_paths": ["stem", "option", "answer", "solution"],
    }
    assert layout(question) == {
        "review": False,
        "stem": [0],
        "options": [[1], []],
        "answer": [2],
        "solution": [3],
    }
    media = SimpleNamespace(url=lambda path: path)
    public = question_images(media, question)
    assert public["image_urls"][0].endswith("/images/0")
    assert len(public["preview_image_urls"]) == 2
    assert solution_images(media, question)["answer_image_urls"][0].endswith(
        "/images/2"
    )
    question["image_paths"].pop()
    assert question_images(media, question)["image_layout_review"] is True
    assert question_images(media, question)["preview_image_urls"] == []


def test_ordinary_attached_figures_and_legacy_fingerprint_format():
    assert layout({"image_paths": ["one", "two"]})["stem"] == [0, 1]
    assert (
        fingerprint_json({"z": 1.0, "a": [True, "方程"]})
        == '{"a": [true, "方程"], "z": 1}'
    )
