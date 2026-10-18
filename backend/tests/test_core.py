import asyncio
import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import cv2
import httpx
import numpy as np
import pytest

from app.auth import create_access_token, hash_password, read_access_token, verify_password
from app.models import Base, DatasetQuestion, KnowledgePoint
from app.providers.api_pool import ApiPoolProvider
from app.schemas import (
    AnalysisOutput,
    CounterfactualRepairProposal,
    CroppedQuestionRecognition,
    DiagnosisOutput,
    HandwrittenAnswerRecognition,
    RawCroppedQuestionRecognition,
    TutorGuidanceOutput,
    VariantOutput,
)
from app.services.ai_pipeline import analyze_question, diagnose_steps, generate_tutor_guidance
from app.services.cognition import cognition_target, update_cognition
from app.services.counterfactual import validate_first_error_counterfactual
from app.services.diagnosis import align_steps
from app.services.export import build_excel, build_pdf
from app.services.grading import grade_answer
from app.services.handwritten_answer import recognize_handwritten_answer
from app.services.image_recognition import (
    CROPPED_RECOGNITION_SYSTEM_PROMPT,
    filter_teacher_annotations_by_red_evidence,
    recognize_cropped_question,
)
from app.services.math_tools import locate_first_error, solve_text_equation, verify_equivalence
from app.services.pedagogy import (
    CORE_SUBJECTS,
    evaluate_teach_back,
    evaluate_understanding_check,
)
from app.services.personal_knowledge_graph import match_knowledge_points
from app.services.practice_retrieval import (
    RetrievalCandidate,
    bge_runtime,
    concept_terms,
    rerank_candidates,
    retrieval_text,
    retrieve_variant_references,
    variant_reference,
)
from app.services.question_mapping import map_question, normalized_grade, student_facing_topic
from app.services.question_quality import quality_flags
from app.services.tutor_activities import (
    activity_public,
    adaptive_teaching_policy,
    build_adaptive_teaching_brief,
    build_understanding_plan,
    build_writing_guidance,
    confirmation_activity,
    writing_help_requested,
)
from app.services.tutor_graph import ensure_fresh_tutor_reply, run_tutor_step
from app.services.tutor_state import canonical_tutor_stage, previous_tutor_stage, transition_tutor_stage
from app.services.variants import (
    build_knowledge_fallback,
    verify_knowledge_alignment,
    verify_variant,
)
from app.services.vision import crop_image, persist_recognition_regions, preprocess_image
from app.services.visualizations import recommended_visualization


def pool_file(tmp_path: Path) -> Path:
    path = tmp_path / "pool.json"
    path.write_text(
        json.dumps(
            {
                "entries": [
                    {"base_url": "https://one.local/v1", "key": "fake-one", "model": "Qwen"},
                    {"base_url": "https://two.local/v1", "key": "fake-two", "model": "Qwen"},
                    {"base_url": "https://three.local/v1", "key": "fake-three", "model": "Qwen"},
                ]
            }
        )
    )
    return path


@pytest.mark.parametrize(
    ("subject", "question_type", "title", "points", "error", "root", "expected"),
    [
        (
            "数学",
            "计算题",
            "参数范围",
            ["二次函数", "边界条件"],
            "condition_omission",
            "漏检端点",
            "二次函数",
        ),
        ("物理", "解答题", "速度计算", ["速度公式", "单位换算"], "unit_error", "速度单位遗漏", "速度公式"),
        ("英语", "填空题", "定语从句", ["关系代词"], "grammar_error", "关系代词使用错误", "关系代词"),
    ],
)
def test_cognition_target_uses_real_cross_subject_context(
    subject,
    question_type,
    title,
    points,
    error,
    root,
    expected,
):
    target = cognition_target(
        subject=subject,
        question_type=question_type,
        title=title,
        question_knowledge_points=points,
        diagnosis_error_type=error,
        diagnosis_root_misconception=root,
    )
    assert target.knowledge_point == expected
    assert target.subject == subject
    assert target.misconception_code == error
    assert target.misconception_label == root
    assert target.knowledge_point != "一元一次方程"


def test_cognition_target_falls_back_to_question_context_without_demo_defaults():
    target = cognition_target(
        subject="历史",
        question_type="材料题",
        title="辛亥革命的影响",
        question_knowledge_points=[],
        diagnosis_error_type=None,
        diagnosis_root_misconception=None,
    )
    assert target.knowledge_point == "辛亥革命的影响"
    assert target.misconception_code == "unclassified"
    assert target.misconception_label == "unclassified"


def test_cognition_update_requires_explicit_target_and_prefers_confirmed_question_mapping():
    signature = inspect.signature(update_cognition)
    assert signature.parameters["knowledge_point"].default is inspect.Parameter.empty
    assert signature.parameters["misconception_code"].default is inspect.Parameter.empty
    assert signature.parameters["subject"].default is inspect.Parameter.empty
    target = cognition_target(
        subject="数学",
        question_type="计算题",
        title="参数题",
        question_knowledge_points=["边界条件"],
        analysis_knowledge_points=["错误的模型输出"],
        diagnosis_error_type="condition_omission",
    )
    assert target.knowledge_point == "边界条件"


def test_password_hash_and_signed_login_token():
    encoded = hash_password("123456")
    assert verify_password("123456", encoded)
    assert not verify_password("654321", encoded)
    token = create_access_token("student-id", "test-secret")
    assert read_access_token(token, "test-secret") == "student-id"
    assert read_access_token(token, "wrong-secret") is None


@pytest.mark.parametrize(
    ("code", "label"),
    [
        ("micro_activity", "小步练习"),
        ("independent_dataset_practice", "独立完成题库练习"),
        ("teacher_review", "教师复核指导"),
    ],
)
def test_learning_strategy_codes_have_student_facing_labels(code, label):
    from app.main import learning_method_label

    assert learning_method_label(code) == label


def test_handwritten_answer_recognition_validates_structured_output():
    result = HandwrittenAnswerRecognition(
        final_answer="x=2",
        steps=["2x=4", "x=2"],
        transcription="2x=4\nx=2",
        confidence=0.91,
    )
    assert result.steps == ["2x=4", "x=2"]
    with pytest.raises(ValueError):
        HandwrittenAnswerRecognition(confidence=1.2)


def test_handwritten_answer_uses_multimodal_structured_recognition(tmp_path: Path):
    image = tmp_path / "working.jpg"
    image.write_bytes(b"student-working")

    class FakeProvider:
        async def generate_multimodal(self, prompt, images, schema, system):
            assert "当前题目：解方程" in prompt
            assert images == [b"student-working"]
            assert schema is HandwrittenAnswerRecognition
            assert "不解题" in system
            return HandwrittenAnswerRecognition(
                final_answer="x=2",
                steps=["2x=4", "x=2"],
                transcription="2x=4\nx=2",
                confidence=0.95,
            )

    result = asyncio.run(
        recognize_handwritten_answer(
            FakeProvider(),
            image,
            question_text="解方程",
            subject="数学",
        )
    )
    assert result.final_answer == "x=2"


def test_pool_rejects_non_qwen_model(tmp_path: Path):
    path = tmp_path / "invalid-pool.json"
    path.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "base_url": "https://invalid.local/v1",
                        "key": "fake",
                        "model": "forbidden-model",
                    }
                ]
            }
        )
    )
    with pytest.raises(ValueError, match="非Qwen"):
        ApiPoolProvider(path)


def test_pool_rejects_non_allowed_provider(tmp_path: Path):
    path = tmp_path / "invalid-provider.json"
    path.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "base_url": "https://forbidden.example/v1",
                        "key": "fake",
                        "model": "Qwen",
                    }
                ]
            }
        )
    )
    with pytest.raises(ValueError, match="非许可提供商"):
        ApiPoolProvider(path, allowed_hosts={"api.chat.csu.edu.cn"})


def test_pool_ignores_disabled_entries(tmp_path: Path):
    path = tmp_path / "disabled-pool.json"
    path.write_text(
        json.dumps(
            {
                "entries": [
                    {"base_url": "https://active.local/v1", "key": "active", "model": "Qwen"},
                    {
                        "base_url": "https://disabled.local/v1",
                        "key": "disabled",
                        "model": "Qwen",
                        "disabled": True,
                    },
                ]
            }
        )
    )
    provider = ApiPoolProvider(path)
    assert len(provider.entries) == 1
    assert provider.entries[0].base_url == "https://active.local/v1"
    asyncio.run(provider.close())


@pytest.mark.asyncio
async def test_pool_round_robin(tmp_path: Path):
    provider = ApiPoolProvider(pool_file(tmp_path))
    first = (await provider._ordered(False))[0].entry_id
    second = (await provider._ordered(False))[0].entry_id
    third = (await provider._ordered(False))[0].entry_id
    fourth = (await provider._ordered(False))[0].entry_id
    assert len({first, second, third}) == 3
    assert fourth == first
    await provider.close()


@pytest.mark.asyncio
async def test_text_and_vision_share_one_global_key_cursor(tmp_path: Path):
    provider = ApiPoolProvider(pool_file(tmp_path))
    first = (await provider._ordered(False))[0].entry_id
    second = (await provider._ordered(True))[0].entry_id
    third = (await provider._ordered(False))[0].entry_id
    fourth = (await provider._ordered(True))[0].entry_id

    assert len({first, second, third}) == 3
    assert fourth == first
    assert provider.health_check()["global_index"] == 1
    assert provider.health_check()["unique_keys"] == 3
    await provider.close()


@pytest.mark.asyncio
async def test_pool_skips_429(tmp_path: Path):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if "one.local" in str(request.url):
            return httpx.Response(429, headers={"Retry-After": "60"})
        return httpx.Response(200, json={"choices": [{"message": {"content": "5"}}]})

    provider = ApiPoolProvider(pool_file(tmp_path))
    await provider._client.aclose()
    provider._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    assert await provider.generate_text("2+3") == "5"
    assert len(calls) == 2
    assert provider.entries[0].cooldown_until > 0
    await provider.generate_text("2+3")
    assert "three.local" in calls[-1]
    await provider.close()


@pytest.mark.asyncio
async def test_transient_probe_failure_never_empties_runtime_pool(tmp_path: Path):
    provider = ApiPoolProvider(pool_file(tmp_path))

    async def fail_probe(*_args, **_kwargs):
        raise httpx.ConnectError("temporary network failure")

    provider._request_entry = fail_probe  # type: ignore[method-assign]
    health = await provider._probe_entries()

    assert len(provider.text_entries) == 3
    assert len(provider.vision_entries) == 3
    assert health["text_entries"] == 3
    assert health["vision_entries"] == 3
    assert health["last_status"] == "degraded"
    await provider.close()


@pytest.mark.asyncio
async def test_structured_output(tmp_path: Path):
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        body = AnalysisOutput(subject="数学", reference_steps=["x=1"], final_answer="x=1").model_dump_json()
        return httpx.Response(200, json={"choices": [{"message": {"content": f"```json\n{body}\n```"}}]})

    provider = ApiPoolProvider(pool_file(tmp_path))
    await provider._client.aclose()
    provider._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await provider.generate_structured("分析", AnalysisOutput)
    assert result.final_answer == "x=1"
    assert requests[0]["response_format"] == {"type": "json_object"}
    assert requests[0]["chat_template_kwargs"] == {"enable_thinking": False}
    assert requests[0]["max_tokens"] == 2048
    await provider.close()


def recognition_payload(**overrides):
    payload = {
        "subject": "数学",
        "grade": None,
        "question_type": "calculation",
        "question_text": "计算 $-18\\div(-\\frac{2}{3})$。",
        "options": [],
        "student_answer": None,
        "student_steps": [],
        "teacher_annotations": [],
        "printed_irrelevant": [],
        "has_answer": False,
        "has_working": False,
        "has_teacher_annotation": False,
        "recognition_confidence": 0.92,
        "uncertain_fields": [],
    }
    payload.update(overrides)
    return payload


def test_cropped_recognition_schema_enforces_real_student_content():
    empty = CroppedQuestionRecognition.model_validate(recognition_payload())
    assert empty.student_answer is None
    assert empty.student_steps == []
    assert CroppedQuestionRecognition.model_validate(recognition_payload(subject="Math")).subject == "数学"

    with pytest.raises(ValueError, match="has_working"):
        CroppedQuestionRecognition.model_validate(recognition_payload(has_working=True))
    with pytest.raises(ValueError, match="has_answer"):
        CroppedQuestionRecognition.model_validate(recognition_payload(student_answer="-27"))
    with pytest.raises(ValueError, match="extra_forbidden"):
        CroppedQuestionRecognition.model_validate(recognition_payload(diagnosis="符号错误"))


def test_cropped_recognition_separates_three_visual_region_roles():
    result = CroppedQuestionRecognition.model_validate(
        recognition_payload(
            question_figures=[
                {
                    "role": "diagram",
                    "bbox": [0.05, 0.1, 0.45, 0.6],
                    "description": "题干印刷的三角形ABC",
                }
            ],
            student_working_figures=[
                {
                    "role": "student_working_figure",
                    "bbox": [0.5, 0.2, 0.9, 0.65],
                    "description": "学生铅笔画的辅助线",
                }
            ],
            teacher_annotation_regions=[
                {
                    "role": "teacher_annotation_region",
                    "bbox": [0.45, 0.7, 0.85, 0.95],
                    "description": "教师红笔圈出的角",
                }
            ],
        )
    )
    assert result.question_figures[0].role == "diagram"
    assert result.student_working_figures[0].role == "student_working_figure"
    assert result.teacher_annotation_regions[0].role == "teacher_annotation_region"
    with pytest.raises(ValueError, match="归一化"):
        CroppedQuestionRecognition.model_validate(
            recognition_payload(
                question_figures=[
                    {
                        "role": "chart",
                        "bbox": [0, 0, 1.2, 1],
                        "description": "越界图",
                    }
                ]
            )
        )


def test_three_visual_region_categories_persist_to_distinct_assets(tmp_path: Path):
    crop = tmp_path / "crop.jpg"
    assert cv2.imwrite(str(crop), np.full((300, 300, 3), 255, dtype=np.uint8))
    recognition = CroppedQuestionRecognition.model_validate(
        recognition_payload(
            question_figures=[
                {
                    "role": "diagram",
                    "bbox": [0, 0, 0.3, 0.3],
                    "description": "原题图",
                }
            ],
            student_working_figures=[
                {
                    "role": "student_working_figure",
                    "bbox": [0.35, 0.35, 0.65, 0.65],
                    "description": "学生草图",
                }
            ],
            teacher_annotation_regions=[
                {
                    "role": "teacher_annotation_region",
                    "bbox": [0.7, 0.7, 1, 1],
                    "description": "教师批注",
                }
            ],
        )
    )

    saved = persist_recognition_regions(crop, tmp_path / "regions", recognition)

    assert {item["kind"] for item in saved} == {
        "question_figure",
        "student_working_figure",
        "teacher_annotation_region",
    }
    assert len({item["path"] for item in saved}) == 3
    assert all(Path(item["path"]).is_file() for item in saved)


def test_teacher_annotation_requires_real_red_ink_not_gray_show_through(tmp_path: Path):
    crop = tmp_path / "gray-show-through.jpg"
    gray = np.full((300, 500, 3), 235, dtype=np.uint8)
    cv2.putText(gray, "A", (120, 150), cv2.FONT_HERSHEY_SIMPLEX, 2, (170, 170, 170), 3)
    assert cv2.imwrite(str(crop), gray)
    recognition = CroppedQuestionRecognition.model_validate(
        recognition_payload(
            teacher_annotations=[{"text": "A", "type": "correction"}],
            teacher_annotation_regions=[
                {
                    "role": "teacher_annotation_region",
                    "bbox": [0.15, 0.2, 0.5, 0.7],
                    "description": "灰色透印字母A",
                }
            ],
            has_teacher_annotation=True,
        )
    )

    filtered = filter_teacher_annotations_by_red_evidence(recognition, crop)

    assert filtered.teacher_annotations == []
    assert filtered.teacher_annotation_regions == []
    assert filtered.has_teacher_annotation is False
    assert "teacher_annotations" in filtered.uncertain_fields


def test_teacher_annotation_with_red_ink_is_preserved(tmp_path: Path):
    crop = tmp_path / "red-correction.jpg"
    red = np.full((300, 500, 3), 245, dtype=np.uint8)
    cv2.putText(red, "A", (120, 150), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 220), 5)
    assert cv2.imwrite(str(crop), red)
    recognition = CroppedQuestionRecognition.model_validate(
        recognition_payload(
            teacher_annotations=[{"text": "A", "type": "correction"}],
            teacher_annotation_regions=[
                {
                    "role": "teacher_annotation_region",
                    "bbox": [0.15, 0.2, 0.5, 0.7],
                    "description": "红笔字母A",
                }
            ],
            has_teacher_annotation=True,
        )
    )

    filtered = filter_teacher_annotations_by_red_evidence(recognition, crop)

    assert filtered.teacher_annotations[0].text == "A"
    assert len(filtered.teacher_annotation_regions) == 1
    assert filtered.has_teacher_annotation is True


@pytest.mark.parametrize(
    ("case_name", "role", "description"),
    [
        ("geometry", "diagram", "几何题中的三角形和辅助圆"),
        ("function", "chart", "函数题中的坐标轴与函数曲线"),
        ("table", "table", "题干给出的实验数据表格"),
        ("physics", "question_figure", "物理题中的斜面和物体示意图"),
    ],
)
def test_four_question_figure_types_are_cropped_and_persisted(
    tmp_path: Path,
    case_name: str,
    role: str,
    description: str,
):
    crop = tmp_path / f"{case_name}.jpg"
    image = np.full((400, 600, 3), 255, dtype=np.uint8)
    cv2.rectangle(image, (60, 80), (540, 320), (0, 0, 0), 5)
    assert cv2.imwrite(str(crop), image)
    recognition = CroppedQuestionRecognition.model_validate(
        recognition_payload(
            question_figures=[
                {
                    "role": role,
                    "bbox": [0.1, 0.2, 0.9, 0.8],
                    "description": description,
                }
            ],
        )
    )

    saved = persist_recognition_regions(crop, tmp_path / case_name, recognition)

    assert len(saved) == 1
    assert saved[0]["kind"] == "question_figure"
    assert saved[0]["role"] == role
    assert saved[0]["bbox"] == [0.1, 0.2, 0.9, 0.8]
    assert Path(saved[0]["path"]).is_file()
    persisted = cv2.imread(saved[0]["path"])
    assert persisted.shape[:2] == (240, 480)


@pytest.mark.asyncio
async def test_qwen_recognition_reads_only_crop_bytes_and_retries_schema_once(tmp_path: Path):
    crop = tmp_path / "crop.jpg"
    crop.write_bytes(b"only-cropped-question")

    class FakeProvider:
        calls: list[dict] = []

        async def generate_multimodal(self, prompt, images, schema, system):
            self.calls.append({"prompt": prompt, "images": images, "schema": schema, "system": system})
            if len(self.calls) == 1:
                return schema.model_validate(recognition_payload(has_working=True))
            return schema.model_validate(
                recognition_payload(
                    student_answer="-27",
                    student_steps=[{"index": 1, "text": "$-18\\times(-\\frac{3}{2})=-27$"}],
                    has_answer=True,
                    has_working=True,
                )
            )

    fake = FakeProvider()
    result = await recognize_cropped_question(fake, crop)  # type: ignore[arg-type]

    assert len(fake.calls) == 2
    assert all(call["images"] == [b"only-cropped-question"] for call in fake.calls)
    assert all(call["schema"] is RawCroppedQuestionRecognition for call in fake.calls)
    assert fake.calls[0]["system"] == CROPPED_RECOGNITION_SYSTEM_PROMPT
    assert result.student_answer == "-27"


@pytest.mark.asyncio
async def test_qwen_zero_to_thousand_bbox_is_normalized_before_business_schema(tmp_path: Path):
    crop = tmp_path / "crop.jpg"
    crop.write_bytes(b"cropped-question-with-chart")

    class FakeProvider:
        async def generate_multimodal(self, prompt, images, schema, system):
            return schema.model_validate(
                recognition_payload(
                    question_figures=[
                        {
                            "role": "chart",
                            "bbox": [120, 80, 920, 760],
                            "description": "函数坐标轴与抛物线",
                        }
                    ]
                )
            )

    result = await recognize_cropped_question(FakeProvider(), crop)  # type: ignore[arg-type]

    assert result.question_figures[0].bbox == [0.12, 0.08, 0.92, 0.76]
    assert max(result.question_figures[0].bbox) <= 1


@pytest.mark.asyncio
async def test_analysis_diagnosis_and_tutor_all_receive_visual_and_student_context(tmp_path: Path):
    crop = tmp_path / "crop.jpg"
    figure = tmp_path / "question_figure.jpg"
    crop.write_bytes(b"crop-image")
    figure.write_bytes(b"figure-image")

    class FakeProvider:
        calls: list[dict] = []

        async def generate_multimodal(self, prompt, images, schema, system):
            self.calls.append({"prompt": prompt, "images": images, "schema": schema, "system": system})
            if schema is AnalysisOutput:
                return AnalysisOutput(reference_steps=["连接OA", "比较角度"], final_answer="证明完成")
            if schema is DiagnosisOutput:
                return DiagnosisOutput(first_error_step=0, first_error_text="漏看图中垂直条件")
            if schema is TutorGuidanceOutput:
                return TutorGuidanceOutput(reply="先看图中的垂直标记，它能推出什么角度关系？")
            raise AssertionError("unexpected schema")

    fake = FakeProvider()
    paths = [crop, figure]
    await analyze_question(
        fake,
        "如图，证明AB平行CD",
        "数学",
        "初二",
        "proof",
        paths,
        "AB∥CD",
        ["连接OA"],
    )
    await diagnose_steps(
        fake,
        "如图，证明AB平行CD",
        ["利用垂直关系"],
        ["连接OA"],
        "数学",
        "proof",
        paths,
        "AB∥CD",
    )
    reply = await generate_tutor_guidance(
        fake,
        visual_paths=paths,
        question_text="如图，证明AB平行CD",
        student_answer="AB∥CD",
        student_steps=["连接OA"],
        subject="数学",
        question_type="proof",
        draft_reply="先观察图形条件。",
    )

    assert len(fake.calls) == 3
    assert all(call["images"] == [b"crop-image", b"figure-image"] for call in fake.calls)
    assert all("如图，证明AB平行CD" in call["prompt"] for call in fake.calls)
    assert all("AB∥CD" in call["prompt"] for call in fake.calls)
    assert all("连接OA" in call["prompt"] for call in fake.calls)
    assert reply.startswith("先看图中的垂直标记")


def test_math_tools():
    assert verify_equivalence("11-3", "8")


def test_geometry_question_recommends_matching_visualization():
    assert recommended_visualization("数学", "几何计算题", ["勾股定理", "直角三角形"]) == "right_triangle"
    assert recommended_visualization("数学", "圆周角证明题", ["圆"]) == "circle"
    assert solve_text_equation("2x+3=11") == ("x=4", True)
    assert locate_first_error(["2x=11-3", "x=4"], ["2x=11+3", "x=7"]) == 0
    assert solve_text_equation("函数图像：=x+2") == ("", False)
    assert solve_text_equation("解方程：(x+2=4") == ("", False)
    malformed = SimpleNamespace(question_text="解方程：(x+2=4", answer="x=2", reference_solution=["x=2"])
    assert verify_variant(malformed, "数学") is False


def test_langgraph_tutor_routing():
    unknown = run_tutor_step(1, "我不知道", 0)
    partial = run_tutor_step(2, "我觉得这部分对，但下一步呢", 1)
    correct_answer = run_tutor_step(3, "x等于4", 2, context={"final_answer": "x=4"})
    assert unknown["stage"] == partial["stage"] == correct_answer["stage"] == "understanding"
    assert unknown["branch"] == "completely_unknown"
    assert partial["branch"] == "partial_correct"
    assert correct_answer["branch"] == "correct_but_unclear"


def test_tutor_hint_request_and_duplicate_reply_are_progressive():
    hint = run_tutor_step(2, "给我一点提示", 1, context={"subject": "数学"})
    method = run_tutor_step(3, "我应该用什么方法", 1, context={"subject": "数学"})
    assert hint["branch"] == method["branch"] == "hint_requested"
    assert hint["reply"] != method["reply"]
    repeated = "先不展开完整答案。只看出错的这一步。"
    fresh = ensure_fresh_tutor_reply(
        repeated,
        repeated,
        [repeated],
        subject="数学",
        branch="guided_question",
        turn_count=2,
    )
    assert fresh != repeated
    assert "换个问法" in fresh or "先只回答" in fresh or "分成两半" in fresh


@pytest.mark.parametrize("subject", CORE_SUBJECTS)
def test_tutor_uses_subject_specific_prerequisites(subject: str):
    result = run_tutor_step(1, "我完全不会", 0, context={"subject": subject, "question_type": "材料题"})
    assert result["stage"] == "understanding"
    assert result["branch"] == "completely_unknown"
    if subject != "数学":
        assert "等式两边" not in result["reply"]
        assert "x=4" not in result["reply"]


@pytest.mark.parametrize(
    ("subject", "explanation"),
    [
        ("数学", "因为根据乘法分配律展开，所以可以得到这个结论。"),
        ("物理", "根据牛顿第二定律，这个过程合力方向不变，所以还要检查单位。"),
        ("化学", "因为反应遵守质量守恒，配平方程式并写出条件，所以得到结论。"),
        ("语文", "根据原文中的动作描写，这句话表现人物紧张，所以支持这个观点。"),
        ("英语", "根据句子语境和already判断时态，所以这里符合现在完成时。"),
        ("生物", "因为实验只改变光照变量，其他条件相同，所以说明光照影响过程。"),
        ("历史", "根据材料中的史实和事件背景，这个原因导致后续影响，所以结论成立。"),
        ("地理", "根据图中位置和地形，气流抬升导致降水，所以这里分布较多。"),
        ("道德与法治", "材料中的行为违反法律规则，因为权利义务统一，所以应该停止侵害。"),
        ("思想政治", "材料体现实践与认识原理，因为实践提出问题，所以推动认识发展。"),
    ],
)
def test_teach_back_is_subject_aware(subject: str, explanation: str):
    result = evaluate_teach_back(explanation, subject, "综合题")
    assert result["passed"] is True, result


def test_understanding_check_is_explicit_and_deterministic():
    assert evaluate_understanding_check("这里要检查边界条件", "数学", ["边界条件"])["passed"] is True
    assert evaluate_understanding_check("我不知道", "数学", ["边界条件"])["passed"] is False
    assert evaluate_understanding_check("答案是 a 小于 1", "数学", ["边界条件"])["passed"] is False


def test_tutor_stage_machine_full_success_path_and_guards():
    state = {"understanding_passed": False}
    with pytest.raises(ValueError, match="先通过理解检查"):
        transition_tutor_stage("understanding", "understanding_advance", state)
    state["understanding_passed"] = True
    stage = transition_tutor_stage("understanding", "understanding_advance", state)
    assert stage == "teach_back"
    stage = transition_tutor_stage(stage, "teach_back_pass", state)
    assert stage == "near_transfer"
    stage = transition_tutor_stage(stage, "near_pass", state)
    assert stage == "far_transfer"
    stage = transition_tutor_stage(stage, "far_pass", state)
    assert stage == "finished"
    with pytest.raises(ValueError, match="不能执行"):
        transition_tutor_stage(stage, "near_pass", state)


def test_tutor_stage_machine_uses_main_stages_for_retries():
    assert canonical_tutor_stage("guided_question") == "understanding"
    assert canonical_tutor_stage("teach_back_retry") == "teach_back"
    assert canonical_tutor_stage("near_remediation") == "near_transfer"
    assert canonical_tutor_stage("transfer_insufficient") == "far_transfer"
    assert transition_tutor_stage("teach_back", "teach_back_fail") == "teach_back"
    assert transition_tutor_stage("teach_back_retry", "teach_back_pass") == "near_transfer"
    assert transition_tutor_stage("near_transfer", "near_fail") == "near_transfer"
    assert transition_tutor_stage("near_remediation", "near_pass") == "far_transfer"
    assert transition_tutor_stage("far_transfer", "far_fail") == "far_transfer"
    assert transition_tutor_stage("transfer_insufficient", "far_pass") == "finished"


def test_tutor_stage_machine_can_return_one_stage_at_a_time():
    assert previous_tutor_stage("far_transfer") == "near_transfer"
    assert previous_tutor_stage("near_transfer") == "teach_back"
    assert previous_tutor_stage("teach_back") == "understanding"
    with pytest.raises(ValueError, match="不能返回上一步"):
        previous_tutor_stage("understanding")


def test_cube_understanding_plan_is_bounded_and_structured():
    plan = build_understanding_plan(
        question_text="把正方体展开图折叠，相对面上的数之和为5",
        subject="数学",
        question_type="填空题",
        knowledge_points=["正方体的展开图", "相对面的判断"],
        reference_steps=["x与4相对，所以x=1"],
    )
    assert 1 <= len(plan) <= 3
    assert plan[0]["type"] == "single_choice"
    correct = asyncio.run(
        grade_answer(
            SimpleNamespace(),
            question=plan[0]["question"],
            answer="4",
            expected=plan[0]["correct_answers"][0],
            reference_solution=[],
            subject="数学",
            question_type=plan[0]["type"],
            options=plan[0]["options"],
        )
    )
    wrong = asyncio.run(
        grade_answer(
            SimpleNamespace(),
            question=plan[0]["question"],
            answer="1",
            expected=plan[0]["correct_answers"][0],
            reference_solution=[],
            subject="数学",
            question_type=plan[0]["type"],
            options=plan[0]["options"],
        )
    )
    assert correct["correct"]
    assert not wrong["correct"]
    fallback = confirmation_activity(plan[0])
    public = activity_public(fallback, attempt=1, teaching=fallback["teaching"])
    assert public["max_attempts"] == 2
    assert public["options"]
    assert "correct_answers" not in public


def test_writing_guidance_turns_reference_steps_into_a_scaffold():
    guidance = build_writing_guidance(
        ["先确定 A 的最大元素", "再确定 B 的最小元素", "按分界点分类计数"],
        expected_answer="16",
    )
    assert guidance.startswith("可以按这个顺序写：")
    assert "1. 先确定 A 的最大元素" in guidance
    assert "4. 最后写出结论：16" in guidance
    assert writing_help_requested("我不知道怎么写，教我一下")
    assert writing_help_requested("没思路")
    assert not writing_help_requested("我先写出已知条件")


def test_adaptive_policy_compresses_simple_answer_only_questions():
    choice = adaptive_teaching_policy(
        "choice",
        options=[{"label": "A", "text": "0有倒数"}],
        student_steps=[],
        correct_answer="D",
    )
    fill = adaptive_teaching_policy(
        "fill_blank",
        options=[],
        student_steps=[],
        correct_answer="2",
    )
    calculation = adaptive_teaching_policy(
        "calculation",
        options=[],
        student_steps=["2x=4", "x=2"],
        correct_answer="x=2",
    )
    assert choice["mode"] == fill["mode"] == "compressed"
    assert choice["skip_teach_back"] and choice["skip_far_transfer"]
    assert calculation["mode"] == "full"


def test_reciprocal_choice_brief_targets_the_actual_distractor():
    class OfflineProvider:
        async def generate_structured(self, *_args, **_kwargs):
            from app.providers.api_pool import ApiPoolUnavailable

            raise ApiPoolUnavailable("offline")

    brief = asyncio.run(
        build_adaptive_teaching_brief(
            OfflineProvider(),
            question_text="下列关于倒数的说法正确的是",
            options=[
                {"label": "A", "text": "0的倒数是0"},
                {"label": "B", "text": "-2的倒数是2"},
                {"label": "C", "text": "正数的倒数是负数"},
                {"label": "D", "text": "一个数的倒数可能大于这个数"},
            ],
            correct_answer="D",
            student_answer="A",
            diagnosis={"root_misconception": "忽略0没有倒数"},
            student_steps=[],
            knowledge_points=["倒数"],
            question_type="choice",
        )
    )
    assert brief.correct_answer == "D"
    assert brief.check.question == "下面哪个数没有倒数？"
    assert len(brief.check.question) <= 45
    assert any(item.label == "A" and "0没有倒数" in item.text for item in brief.option_explanations)


def test_subject_answer_validation():
    async def grade(answer, expected, subject, question_type, options=None):
        return await grade_answer(
            SimpleNamespace(),
            question="test",
            answer=answer,
            expected=expected,
            reference_solution=[],
            subject=subject,
            question_type=question_type,
            options=options,
        )

    assert asyncio.run(grade("x=4", "x=4", "数学", "填空题"))["correct"]
    assert asyncio.run(grade("14m/s", "14m/s", "物理", "填空题"))["correct"]
    assert not asyncio.run(grade("14", "14m/s", "物理", "填空题"))["correct"]
    assert asyncio.run(grade("B", "B", "英语", "选择题", [{"key": "B"}]))["correct"]
    assert asyncio.run(grade(["B", "D"], ["B", "D"], "数学", "多选题", [{"key": "B"}]))["correct"]


def test_internal_question_type_never_becomes_homepage_topic():
    assert student_facing_topic([], "fill_blank") == "填空题"
    assert student_facing_topic(["fill_blank"], "other") == "填空题"
    assert student_facing_topic(["二次函数"], "calculation") == "二次函数"
    history = asyncio.run(
        grade_answer(
            SimpleNamespace(),
            question="原因",
            answer="短期事件是直接原因，长期社会矛盾是根本原因",
            expected="短期事件是直接原因，长期社会矛盾是根本原因",
            reference_solution=[],
            subject="历史",
            question_type="填空题",
        )
    )
    assert history["correct"]


def test_variant_fallback_and_validation_stay_on_cube_knowledge():
    points = ["正方体的展开图", "正方体相对面的判断"]
    context = "正方体表面展开图折叠后，判断相对面"
    unrelated = VariantOutput(
        question_text="解方程：3x+5=20",
        answer="x=5",
        reference_solution=["3x=15", "x=5"],
        explanation="练习等价变形",
    )
    assert not verify_knowledge_alignment(unrelated, points, context)
    ambiguous = VariantOutput(
        question_text="如图是正方体展开图，第一行：[2]，第二行：[x][3][4][y]，第三行：[1]，判断相对面。",
        answer="7",
        reference_solution=["判断相对面"],
        explanation="练习正方体展开图折叠",
    )
    assert not verify_knowledge_alignment(ambiguous, points, context)
    for transfer in ("near", "far"):
        item, source = build_knowledge_fallback("数学", transfer, context, "填空题", points, [])
        assert source == "knowledge_cube_fallback"
        assert verify_variant(item, "数学")
        assert verify_knowledge_alignment(item, points, context)
        assert "解方程" not in item.question_text
    assert {"正方体", "展开图", "相对面"}.issubset(set(concept_terms(points, context)))
    result = asyncio.run(
        grade_answer(
            SimpleNamespace(),
            question="Complete the sentence",
            answer="has finished",
            expected="has finished",
            reference_solution=[],
            subject="英语",
            question_type="填空题",
        )
    )
    assert result["correct"]


def test_grading_uses_explicit_final_conclusion():
    class InvalidProvider:
        async def generate_structured(self, *_args, **_kwargs):
            raise ValueError("invalid model output")

    provider = InvalidProvider()
    working = """当A最大值为1时，共15个
当A最大值为2时，共14个
综上，集合对的个数为 49 个
49"""
    result = asyncio.run(
        grade_answer(
            provider,
            question="求集合对个数",
            answer=working,
            expected="49",
            reference_solution=[],
            subject="数学",
            question_type="填空题",
        )
    )
    assert result["correct"]
    assert result["recognized_answer"] == "49"
    assert "与标准答案一致" in result["feedback"]

    wrong = asyncio.run(
        grade_answer(
            provider,
            question="求集合对个数",
            answer="综上，集合对的个数为47个",
            expected="49",
            reference_solution=[],
            subject="数学",
            question_type="填空题",
        )
    )
    assert not wrong["correct"]
    assert "47" in wrong["feedback"]
    assert "49" in wrong["feedback"]

    conflicting = asyncio.run(
        grade_answer(
            provider,
            question="求集合对个数",
            answer="综上，计算式写成29+12+6=47\n但答案栏误写49",
            expected="49",
            reference_solution=[],
            subject="数学",
            question_type="填空题",
        )
    )
    assert conflicting["can_update_learning"] is False
    assert "误写49" in conflicting["recognized_answer"]


def test_complement_variant_rejects_unrelated_set_counting_question():
    unrelated = VariantOutput(
        question_text="集合P有5个元素，求满足条件的子集对个数。",
        answer="49",
        reference_solution=["分类计数"],
        explanation="集合计数",
    )
    assert not verify_knowledge_alignment(
        unrelated,
        ["集合的补集运算"],
        "求集合B在实数集中的补集",
    )


def test_complement_fallback_is_a_real_complement_question():
    for transfer in ("near", "far"):
        item, source = build_knowledge_fallback(
            "数学",
            transfer,
            "集合的补集运算与并集运算",
            "multiple_choice",
            ["集合的补集运算", "集合的并集运算"],
            [],
        )
        assert source == "knowledge_complement_fallback"
        assert "补集" in item.question_text
        assert item.answer == "A"
        assert len(item.options) == 4
        assert verify_knowledge_alignment(
            item,
            ["集合的补集运算", "集合的并集运算"],
            "集合的补集运算",
        )


@pytest.mark.asyncio
async def test_long_variant_answer_is_graded_by_llm():
    class FakeProvider:
        async def generate_structured(self, prompt, schema, system=""):
            assert "学生作答" in prompt
            assert "严谨的中学作业判题老师" in system
            return schema(
                correct=True,
                score=100,
                recognized_final_answer="49",
                reason="你的分类计数与最终答案49都正确。",
                matched_key_steps=["按A的最大值分类"],
                error_points=[],
                confidence=0.98,
            )

    result = await grade_answer(
        FakeProvider(),
        question="求集合对个数",
        answer="分四种情况计算。\n15+14+12+8=49。\n答案为49。",
        expected="49",
        reference_solution=["分类计数"],
        subject="数学",
        question_type="综合题",
    )
    assert result["correct"]
    assert result["grader"] == "llm"
    assert result["feedback"] == "你的分类计数与最终答案49都正确。"
    assert result["verdict"] == "confirmed_correct"
    assert result["can_update_learning"] is True


@pytest.mark.asyncio
async def test_grading_blocks_rule_and_llm_conflict():
    class ConflictingProvider:
        async def generate_structured(self, _prompt, schema, system=""):
            return schema(
                correct=False,
                score=40,
                recognized_final_answer="49",
                reason="过程中有一处疑似问题。",
                matched_key_steps=[],
                error_points=["分类过程"],
                confidence=0.92,
            )

    result = await grade_answer(
        ConflictingProvider(),
        question="求集合对个数",
        answer="分四种情况计算。\n15+14+12+8=49。\n答案为49。",
        expected="49",
        reference_solution=["分类计数"],
        subject="数学",
        question_type="综合题",
    )
    assert result["verdict"] == "review_required"
    assert result["conflict"] is True
    assert result["can_update_learning"] is False


@pytest.mark.asyncio
async def test_open_answer_is_only_probable_without_rule_proof():
    class AgreeingProvider:
        async def generate_structured(self, _prompt, schema, system=""):
            return schema(
                correct=True,
                score=90,
                recognized_final_answer="略",
                reason="论证思路成立。",
                matched_key_steps=["关键条件"],
                error_points=[],
                confidence=0.9,
            )

    result = await grade_answer(
        AgreeingProvider(),
        question="说明形成原因",
        answer="先依据材料确定条件，再由条件推出结论，最后排除另一种可能。",
        expected="根据关键条件推出结论",
        reference_solution=["提取条件", "推出结论"],
        subject="历史",
        question_type="材料综合题",
    )
    assert result["verdict"] == "probably_correct"
    assert result["correct"] is True
    assert result["can_update_learning"] is False


def test_vision_red_mask(tmp_path: Path):
    image = np.full((160, 300, 3), 255, dtype=np.uint8)
    cv2.putText(image, "2x+3=11", (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
    cv2.line(image, (30, 100), (250, 100), (0, 0, 255), 5)
    original = tmp_path / "original.jpg"
    cv2.imwrite(str(original), image)
    result = preprocess_image(
        original, tmp_path / "clean.jpg", tmp_path / "mask.png", tmp_path / "overlay.jpg"
    )
    assert result["red_ratio"] > 0
    assert (tmp_path / "clean.jpg").exists()


def test_crop_uses_normalized_box_preserves_original_and_caps_ocr_size(tmp_path: Path):
    original = tmp_path / "original.jpg"
    target = tmp_path / "crop.jpg"
    image = np.full((100, 4100, 3), 255, dtype=np.uint8)
    cv2.imwrite(str(original), image)
    original_digest = original.read_bytes()

    result = crop_image(original, target, [0, 0, 1, 1])

    assert original.read_bytes() == original_digest
    assert result["source_width"] == 4100
    assert result["width"] == 1536
    assert result["resized_for_ocr"] is True
    assert target.exists()


def test_exports(tmp_path: Path):
    questions = [{"question_text": "解方程：2x+3=11", "answer": "x=4", "explanation": "移项。"}]
    assert build_pdf(tmp_path / "paper.pdf", "错题帮", questions).stat().st_size > 500
    assert build_excel(tmp_path / "data.xlsx", [{"question": "2x+3=11"}]).stat().st_size > 500


def test_all_business_tables_present():
    assert len(Base.metadata.tables) == 48
    assert "users" in Base.metadata.tables
    assert "tutor_sessions" in Base.metadata.tables
    assert "teacher_marks" in Base.metadata.tables
    assert "cognitive_updates" in Base.metadata.tables
    assert "voice_records" in Base.metadata.tables
    assert {"dataset_sources", "dataset_questions"} <= set(Base.metadata.tables)
    assert {"question_knowledge_links", "practice_recommendations", "dataset_practice_attempts"} <= set(
        Base.metadata.tables
    )
    assert "user_question_knowledge_links" in Base.metadata.tables
    assert {
        "teacher_questions",
        "question_assignments",
        "assignment_students",
        "assignment_attempts",
        "teacher_review_tasks",
        "teacher_review_results",
        "teacher_audit_logs",
    } <= set(Base.metadata.tables)


def dataset_question(**overrides):
    values = {
        "dataset_source_id": "source",
        "source_item_id": "item",
        "split": "train",
        "subject": "数学",
        "grade": "高一",
        "grade_band": "高中",
        "title": "参数题",
        "question_text": "求参数 a 的取值范围",
        "question_type": "选择题",
        "options": [{"key": "A", "text": "a≤1"}, {"key": "B", "text": "a>1"}],
        "answer": "A",
        "solution": "检查等号边界",
        "knowledge_points": ["参数讨论"],
        "image_paths": [],
        "difficulty": "中等",
        "content_hash": "hash",
        "source_metadata": {},
    }
    values.update(overrides)
    return DatasetQuestion(**values)


def test_question_quality_isolates_unanswered_split(tmp_path: Path):
    question = dataset_question(answer=None, solution="", options=[])
    flags = quality_flags(question, tmp_path)
    assert flags["quality_status"] == "no_answer"
    assert flags["usable_for_practice"] is False
    assert flags["usable_for_auto_grade"] is False


def test_retrieval_text_never_contains_answer_or_solution():
    question = dataset_question(answer="SECRET_ANSWER", solution="SECRET_SOLUTION")
    text = retrieval_text(question, ["参数讨论", "边界条件"])
    assert "SECRET_ANSWER" not in text
    assert "SECRET_SOLUTION" not in text
    assert "参数讨论" in text


def test_offline_mapping_uses_subject_grade_knowledge_cards():
    question = dataset_question(question_text="二次函数参数取值范围需要检查端点和等号")
    cards = [
        SimpleNamespace(
            id="boundary",
            code="math-boundary",
            name="边界条件",
            content={"grade": "高一", "chapter": "参数讨论"},
        ),
        SimpleNamespace(
            id="force",
            code="physics-force",
            name="受力对象",
            content={"grade": "高一", "chapter": "受力分析"},
        ),
    ]
    matches = map_question(question, cards)
    assert matches[0].knowledge_id == "boundary"
    assert matches[0].role == "primary"
    assert normalized_grade("七年级上", "初中") == "初一"


@pytest.mark.asyncio
async def test_reinforce_and_variation_are_mode_ranked(monkeypatch):
    same_type = RetrievalCandidate(
        dataset_question(source_item_id="same", question_type="参数题"), "cmm_math", [], 1, 1, 1, 1.0
    )
    different_type = RetrievalCandidate(
        dataset_question(source_item_id="different", question_type="选择题"), "cmm_math", [], 2, 2, 2, 0.9
    )
    monkeypatch.setattr(bge_runtime, "rerank", lambda _query, documents: [0.5] * len(documents))
    reinforced = await rerank_candidates(
        "参数边界", "原始参数题", "参数题", "reinforce", [same_type, different_type]
    )
    assert reinforced[0].question.source_item_id == "same"
    varied = await rerank_candidates(
        "参数边界", "原始参数题", "参数题", "variation", [same_type, different_type]
    )
    assert varied[0].question.source_item_id == "different"


def test_tutor_variant_reference_uses_the_shared_retrieval_candidate():
    candidate = RetrievalCandidate(
        dataset_question(source_item_id="real", question_text="参数题（ ）"),
        "cmm_math",
        [{"id": "boundary", "name": "边界条件", "role": "primary"}],
        1,
        2,
        1,
        0.8,
        reranker_score=0.9,
        mode_score=1.1,
    )
    reference = variant_reference(candidate)
    assert reference.id == candidate.question.id
    assert "A. a≤1" in reference.question_text
    assert reference.answer == "A"
    assert reference.knowledge_points[0]["name"] == "边界条件"
    assert reference.score == 1.1


@pytest.mark.asyncio
async def test_tutor_variant_retrieval_uses_bge_qdrant_reranker_and_exclusions(monkeypatch):
    included = RetrievalCandidate(
        dataset_question(id="included", source_item_id="included", question_text="二次函数边界题"),
        "cmm_math",
        [],
        1,
        1,
        1,
        0.9,
    )
    excluded = RetrievalCandidate(
        dataset_question(id="excluded", source_item_id="excluded", question_text="另一道边界题"),
        "cmm_math",
        [],
        2,
        2,
        2,
        0.8,
    )
    calls: list[str] = []

    async def fake_hybrid(query, subject, grade, grade_band):
        calls.append(f"hybrid:{subject}:{grade}:{grade_band}:{query}")
        return [SimpleNamespace()], {}, {}

    async def fake_load(_db, _fused, _dense, _sparse):
        return [excluded, included]

    async def fake_rerank(query, original, question_type, mode, candidates):
        calls.append(f"rerank:{question_type}:{mode}:{query}:{original}")
        assert candidates == [included]
        included.mode_score = 1.2
        return candidates

    monkeypatch.setattr("app.services.practice_retrieval.hybrid_ids", fake_hybrid)
    monkeypatch.setattr("app.services.practice_retrieval.load_candidates", fake_load)
    monkeypatch.setattr("app.services.practice_retrieval.rerank_candidates", fake_rerank)
    references = await retrieve_variant_references(
        SimpleNamespace(),
        subject="数学",
        grade="高一",
        question_type="参数题",
        knowledge_points=["边界条件"],
        original_text="原始参数题",
        transfer_type="far",
        excluded_question_ids={"excluded"},
    )
    assert [item.id for item in references] == ["included"]
    assert calls[0].startswith("hybrid:数学:高一:高中:")
    assert calls[1].startswith("rerank:参数题:variation:")


def test_alignment_skips_original_condition_and_marks_propagation():
    refs = [
        SimpleNamespace(id="r0", text="2x+3=11"),
        SimpleNamespace(id="r1", text="2x=11-3"),
        SimpleNamespace(id="r2", text="x=4"),
    ]
    students = [SimpleNamespace(id="s0", text="2x=11+3"), SimpleNamespace(id="s1", text="x=7")]
    result = align_steps(refs, students, "数学", "解方程：2x+3=11")
    assert result[0]["alignment"] == "sign_error"
    assert result[0]["is_first_error"] is True
    assert result[1]["propagated"] is True


@pytest.mark.asyncio
async def test_counterfactual_confirms_first_error_after_minimal_repair():
    class FakeProvider:
        async def generate_structured(self, *_args, **_kwargs):
            return CounterfactualRepairProposal(
                corrected_first_step="2x=11-3",
                repaired_steps=["2x=11-3", "x=4"],
                reasoning="移项时改变符号。",
                confidence=0.94,
            )

    alignment = [
        {
            "index": 0,
            "reference_text": "2x=11-3",
            "student_text": "2x=11+3",
            "equivalent": False,
            "is_first_error": True,
            "propagated": False,
            "alignment": "sign_error",
        },
        {
            "index": 1,
            "reference_text": "x=4",
            "student_text": "x=7",
            "equivalent": False,
            "is_first_error": False,
            "propagated": True,
            "alignment": "calculation_error",
        },
    ]
    result = await validate_first_error_counterfactual(
        FakeProvider(),
        question_text="解方程：2x+3=11",
        subject="数学",
        alignment=alignment,  # type: ignore[arg-type]
    )
    assert result["status"] == "confirmed"
    assert result["root_cause_confirmed"] is True
    assert result["recovered_steps"] == 2


def test_personal_graph_only_matches_existing_knowledge_cards():
    cards = [
        KnowledgePoint(id="k1", code="set-complement", subject="数学", name="集合的补集运算", content={}),
        KnowledgePoint(id="k2", code="quadratic", subject="数学", name="一元二次方程", content={}),
    ]
    matches = match_knowledge_points(
        [("集合的补集运算", "primary"), ("模型随口生成的陌生概念", "primary")],
        cards,
    )
    assert [(item["knowledge_point_id"], item["role"]) for item in matches] == [("k1", "primary")]
