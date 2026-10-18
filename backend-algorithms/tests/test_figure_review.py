import asyncio
import base64
import io

import pytest
from app.schemas import HandwrittenAnswerRecognition
from figure_review import FigureHandwritingRecognition, FigureObservation, review_figure
from learning_task_compute import Checkpoint, TaskAction, TaskContext, execute_task
from PIL import Image
from pydantic import ValidationError

SOURCE = "在三角形ABC中，∠A=50°，∠B=60°，求∠C。"


def observed(value="80", **extra):
    return {
        "relation": "angle_value",
        "points": ["A", "C", "B"],
        "value": value,
        "basis": "label",
        "quote": "∠ACB=" + value + "°",
        **extra,
    }


def recognized(*items):
    return FigureHandwritingRecognition(
        final_answer="80",
        transcription="；".join(item["quote"] for item in items),
        figure_observations=items,
        confidence=0.9,
    )


def test_triangle_checks_use_given_conditions_and_keep_visual_guesses_unconfirmed():
    items = [
        observed(),
        observed("70"),
        observed("50", points=["A"]),
        observed("40", basis="appearance"),
    ]
    result = review_figure(SOURCE, recognized(*items))
    assert [row.status for row in result] == [
        "conflicts",
        "consistent_derived",
        "matches_given",
        "unconfirmed",
    ]
    assert "70" not in result[0].message  # No automatic solution reveal.
    assert result[0].source_quote == "∠A=50°；∠B=60°"
    bad_quote = recognized(observed())
    bad_quote.transcription = "没有角度标注"
    assert review_figure(SOURCE, bad_quote)[0].status == "unconfirmed"


def test_goals_options_ambiguous_triangles_and_conflicting_givens_are_not_facts():
    for source in (
        "求证三角形ABC中∠A=50°，∠B=60°。",
        "下列说法中，三角形ABC的∠A=50°，∠B=60°。",
        "在三角形ABC和三角形DEF中，∠A=50°，∠B=60°。",
        "三角形ABC，∠A=50°，∠A=40°，∠B=60°。",
        "三角形ABC，∠A=120°，∠B=80°。",
    ):
        assert review_figure(source, recognized(observed()))[0].status == "unconfirmed"
    assert (
        review_figure(SOURCE + "判断∠C=80°是否成立。", recognized(observed()))[0].status
        == "conflicts"
    )


def test_explicit_relations_support_shared_endpoints_and_reverse_direction():
    item = {
        "relation": "perpendicular",
        "points": ["B", "A", "B", "C"],
        "basis": "mark",
        "quote": "AB⊥BC",
    }
    assert (
        review_figure("已知AB⊥BC，求∠ABC。", recognized(item))[0].status
        == "matches_given"
    )
    assert review_figure("求证AB⊥BC。", recognized(item))[0].status == "unconfirmed"
    collinear = {
        "relation": "collinear",
        "points": ["C", "A", "B"],
        "basis": "label",
        "quote": "C、A、B共线",
    }
    assert (
        review_figure("已知A、B、C三点共线，求角度。", recognized(collinear))[0].status
        == "matches_given"
    )


@pytest.mark.parametrize(
    "item",
    [
        observed("10000000"),
        observed("nan"),
        observed(points=["A", "A", "B"]),
        observed(points=["A", "B"]),
        {**observed(), "script": "javascript"},
        {**observed(), "points": ["<script>"]},
    ],
)
def test_invalid_observation_structure_is_rejected(item):
    with pytest.raises(ValidationError):
        FigureObservation.model_validate(item)


def test_geometry_photo_is_audited_assistance_and_never_independent_mastery():
    class Reader:
        async def generate_multimodal(self, prompt, images, schema, **_):
            assert "不解题" in prompt and images
            assert schema is FigureHandwritingRecognition
            return recognized(observed())

    stream = io.BytesIO()
    Image.new("RGB", (30, 20), "white").save(stream, format="PNG")
    context = TaskContext(
        question_id="q1",
        question_text=SOURCE,
        expected="70",
        student_steps=[],
        question_type="填空题",
    )
    photo = asyncio.run(
        execute_task(
            Reader(),
            context,
            Checkpoint(),
            TaskAction(
                kind="recognize_handwriting",
                handwriting_id="photo1",
                image_base64=base64.b64encode(stream.getvalue()).decode(),
            ),
        )
    )
    assert (
        photo.checkpoint.assistance["independent"] is True
        and not photo.learning_eligible
    )
    assert [trace.tool_name for trace in photo.traces] == [
        "recognize_handwriting",
        "inspect_figure",
    ]
    assert photo.traces[1].evidence["classification"] == "model_observation"
    assert not photo.traces[1].evidence["student_confirmed"]
    assert photo.student_view.model_dump()["handwriting"]["recognition"][
        "figure_observations"
    ]
    assert photo.student_view.handwriting.figure_review[0].status == "conflicts"
    answer = asyncio.run(
        execute_task(
            Reader(),
            context,
            photo.checkpoint,
            TaskAction(
                kind="answer",
                text="70",
                handwriting_id="photo1",
                handwriting_confirmed=True,
                handwriting_recognition=photo.student_view.handwriting.recognition,
            ),
        )
    )
    assert answer.attempt["verdict"] == "confirmed_correct"
    assert answer.attempt["assisted"] and not answer.learning_eligible
    assert answer.checkpoint.phase == "done"


def test_legacy_handwriting_remains_compatible_and_has_no_figure_claims():
    assert (
        review_figure(SOURCE, HandwrittenAnswerRecognition(transcription="∠C=70°"))
        == []
    )


@pytest.mark.parametrize("value", ["80°", "80度", r"80^{\circ}", r"$80^\circ$", 80])
def test_degree_unit_normalization_preserves_value_without_relaxing_validation(value):
    item = FigureObservation.model_validate({**observed(), "value": value})
    assert item.value == "80"
    assert (
        review_figure(SOURCE, recognized({**item.model_dump(), "quote": "∠C=80°"}))[
            0
        ].status
        == "conflicts"
    )


def test_claims_and_implications_are_not_promoted_to_given_angles():
    for text in (
        "在三角形ABC中，若∠A=50°则∠B=60°，求∠C。",
        "小明声称三角形ABC中∠A=50°、∠B=60°，判断是否正确。",
        "三角形ABC中∠A不为50°，∠B=60°，∠C=70°，求∠A。",
    ):
        assert review_figure(text, recognized(observed()))[0].status == "unconfirmed"
    assert (
        review_figure(
            "在三角形ABC中，∠A=50°、∠B=60°，小明认为∠C=80°。", recognized(observed())
        )[0].status
        == "conflicts"
    )


def test_wrong_angle_values_and_common_side_identity_are_observable_not_parser_failures():
    for value in ("190°", "0度", "-30", "720"):
        r = recognized({**observed(), "value": value})
        assert review_figure(SOURCE, r)[0].status == "conflicts"
    item = {
        "relation": "equal_length",
        "points": ["A", "B", "B", "A"],
        "basis": "label",
        "quote": "AB=BA",
    }
    assert (
        review_figure("如图，在几何题中核对公共边。", recognized(item))[0].status
        == "consistent_derived"
    )
    item.update(relation="perpendicular", quote="AB⊥BA")
    assert review_figure("已知AB⊥BA。", recognized(item))[0].status == "unconfirmed"
