"""Diagnosis generation/read, evidence ownership, rollback and stale-input checks."""

import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from smoke_cangjie_accounts import request
from smoke_cangjie_detail import fixture_insert


def diagnoses(endpoint, env, query, token, other, state, started, release):
    def create(steps=None):
        return request(
            endpoint,
            "POST",
            "/api/v1/questions/manual",
            {
                "question_text": "解方程：2*x+3=11",
                "student_answer": "5",
                "student_steps": ["2*x=10", "x=5"] if steps is None else steps,
            },
            token=token,
        )

    def base(q):
        return f"/api/v1/questions/{q['id']}"

    state["diagnosing"] = True
    state["mode"] = "good"
    state["analysis_result"] = {
        "known_conditions": ["2*x+3=11"],
        "knowledge_points": ["方程求解"],
        "prerequisites": [],
        "reference_steps": ["2*x=8", "x=4"],
        "final_answer": "x=4",
    }
    state["diagnosis_result"] = {
        "first_error_step": 99,
        "first_error_text": "不可信位置",
        "root_misconception": "移项时计算错误",
        "strategy_candidates": ["先计算 11-3"],
        "missing_prerequisites": ["诊断专用前置知识"],
        "confidence": 0.8,
    }
    state["repair_result"] = {
        "corrected_first_step": "2*x=8",
        "repaired_steps": ["2*x=8", "x=4"],
        "confidence": 0.9,
    }
    insert = fixture_insert(env, query)
    card = insert(
        "knowledge_points",
        code=f"diagnosis-{uuid4()}",
        subject="数学",
        name="诊断专用前置知识",
        content={},
    )
    try:
        q = create()
        path = base(q)
        request(endpoint, "POST", path + "/diagnose", expected=401)
        request(endpoint, "GET", path + "/diagnosis", expected=401)
        for method, suffix in (("POST", "/diagnose"), ("GET", "/diagnosis")):
            request(endpoint, method, path + suffix, token=other, expected=404)
        assert request(endpoint, "GET", path + "/diagnosis", token=token) is None
        query(env, f"UPDATE questions SET confirmed=0 WHERE id='{q['id']}'")
        request(endpoint, "POST", path + "/diagnose", token=token, expected=409)
        request(endpoint, "POST", path + "/confirm", {}, token=token)
        result = request(endpoint, "POST", path + "/diagnose", token=token)
        assert (
            result["first_error_step"] == 0 and result["first_error_text"] == "2*x=10"
        )
        assert result["counterfactual"]["root_cause_confirmed"] is True
        assert len(result["evidence"]) == 2
        assert (
            query(
                env,
                f"SELECT COUNT(*) FROM problem_analyses WHERE question_id='{q['id']}'",
            )
            == "1"
        )
        assert (
            query(
                env,
                f"SELECT COUNT(*) FROM user_question_knowledge_links WHERE question_id='{q['id']}' AND knowledge_point_id='{card}' AND role='prerequisite'",
            )
            == "1"
        )
        read = request(endpoint, "GET", path + "/diagnosis", token=token)
        assert read["id"] == result["id"] and len(read["evidence"]) == 2
        assert read["counterfactual"] == result["counterfactual"]
        assert {row["reference_step_id"] for row in read["evidence"]} == {
            row["reference_step_id"] for row in result["evidence"]
        }
        latest = request(endpoint, "POST", path + "/diagnose", token=token)
        assert latest["id"] != result["id"]
        assert (
            request(endpoint, "GET", path + "/diagnosis", token=token)["id"]
            == latest["id"]
        )
        assert (
            query(env, f"SELECT COUNT(*) FROM diagnoses WHERE question_id='{q['id']}'")
            == "2"
        )
        assert (
            query(
                env,
                f"SELECT COUNT(*) FROM diagnosis_evidence e JOIN diagnoses d ON e.diagnosis_id=d.id WHERE d.question_id='{q['id']}'",
            )
            == "6"
        )
        query(env, f"UPDATE questions SET status='analyzed' WHERE id='{q['id']}'")
        query(
            env,
            f"ALTER TABLE questions ADD CONSTRAINT diagnosis_failure CHECK (id <> '{q['id']}' OR status <> 'diagnosed')",
        )
        try:
            request(endpoint, "POST", path + "/diagnose", token=token, expected=503)
            assert (
                query(
                    env, f"SELECT COUNT(*) FROM diagnoses WHERE question_id='{q['id']}'"
                )
                == "2"
            )
            assert (
                query(
                    env,
                    f"SELECT COUNT(*) FROM diagnosis_evidence e JOIN diagnoses d ON e.diagnosis_id=d.id WHERE d.question_id='{q['id']}'",
                )
                == "6"
            )
            assert (
                request(endpoint, "GET", path + "/diagnosis", token=token)["id"]
                == latest["id"]
            )
        finally:
            query(env, "ALTER TABLE questions DROP CHECK diagnosis_failure")
        answer_only = create([])
        no_steps = request(
            endpoint, "POST", base(answer_only) + "/diagnose", token=token
        )
        assert no_steps["first_error_step"] is None
        assert no_steps["counterfactual"]["status"] == "not_needed"
        assert not any(e["is_first_error"] for e in no_steps["evidence"])
        for complete in (False, True):
            polynomial = request(
                endpoint,
                "POST",
                "/api/v1/questions/manual",
                {
                    "question_text": "解方程：x^2-5x+6=0，写出所有实数解。",
                    "subject": "数学",
                    "student_answer": "x=2 或 x=3" if complete else "x=2",
                    "student_steps": [
                        "(x-2)(x-3)=0",
                        "x=2 或 x=3" if complete else "x=2",
                    ],
                },
                token=token,
            )
            analysis_id = insert(
                "problem_analyses",
                question_id=polynomial["id"],
                subject="数学",
                final_answer="x=2 或 x=3",
            )
            for index, text in enumerate(
                [
                    "先找乘积为6的两个数。",
                    "再将方程因式分解。",
                    "(x-2)(x-3)=0",
                    "分别求两个因式的解。",
                ]
            ):
                insert(
                    "reference_steps",
                    analysis_id=analysis_id,
                    step_index=index,
                    text=text,
                )
            checked = request(
                endpoint, "POST", base(polynomial) + "/diagnose", token=token
            )
            assert len(checked["evidence"]) == 2
            assert (
                checked["evidence"][0]["math_valid"]
                and not checked["evidence"][0]["is_first_error"]
            )
            if complete:
                assert (
                    checked["first_error_step"] is None
                    and checked["error_type"] == "exact"
                )
                assert (
                    checked["root_misconception"] == ""
                    and checked["missing_prerequisites"] == []
                )
            else:
                assert (
                    checked["first_error_step"] == 1
                    and checked["error_type"] == "condition_omission"
                )
            reread = request(
                endpoint, "GET", base(polynomial) + "/diagnosis", token=token
            )
            assert reread["first_error_step"] == checked["first_error_step"]
            assert (
                reread["evidence"][0]["metadata_json"]["verification_scope"]
                == "original_equation_real_roots"
            )
        previous = {
            key: state[key]
            for key in ("analysis_result", "diagnosis_result", "repair_result")
        }
        try:
            state["analysis_result"] = {
                "known_conditions": ["x^2-5x+6≤0"],
                "knowledge_points": ["一元二次不等式"],
                "reference_steps": ["先找零点，再确定范围。", "(x-2)(x-3)≤0", "2≤x≤3"],
                "final_answer": "x≤2或x≥3",
            }
            state["diagnosis_result"] = {
                "first_error_step": 99,
                "first_error_text": "错误的模型位置",
                "root_misconception": "乘积小于等于零时，需要核对两根之间的范围与端点。",
                "confidence": 0.9,
            }
            state["repair_result"] = {
                "corrected_first_step": "2≤x≤3",
                "repaired_steps": ["(x-2)(x-3)≤0", "2≤x≤3"],
                "confidence": 0.99,
            }
            for complete in (False, True):
                answer = "2≤x≤3" if complete else "x≤2或x≥3"
                item = request(
                    endpoint,
                    "POST",
                    "/api/v1/questions/manual",
                    {
                        "question_text": "解不等式：x^2-5x+6≤0，写出解集。",
                        "subject": "数学",
                        "grade": "高一",
                        "student_answer": answer,
                        "student_steps": ["(x-2)(x-3)≤0", answer],
                    },
                    token=token,
                )
                analyzed = request(
                    endpoint, "POST", base(item) + "/analyze", token=token
                )
                assert analyzed["verified"] and analyzed["final_answer"] == "x ∈ [2, 3]"
                checked = request(
                    endpoint, "POST", base(item) + "/diagnose", token=token
                )
                assert (
                    checked["evidence"][0]["math_valid"]
                    and not checked["evidence"][0]["is_first_error"]
                )
                assert checked["first_error_step"] == (None if complete else 1)
                if complete:
                    assert checked["error_type"] == "exact"
                else:
                    assert checked["counterfactual"]["root_cause_confirmed"]
                    assert (
                        checked["counterfactual"]["repaired_steps"][0] == "(x-2)(x-3)≤0"
                    )
                    state["inequality_question"] = item
                reread = request(
                    endpoint, "GET", base(item) + "/diagnosis", token=token
                )
                assert (
                    reread["evidence"][0]["metadata_json"]["verification_scope"]
                    == "original_inequality_real_solution_set"
                )
                assert reread["first_error_step"] == checked["first_error_step"]
        finally:
            state.update(previous)
        for action in ("work", "archive"):
            item = create()
            item_path = base(item)
            request(endpoint, "POST", item_path + "/analyze", token=token)
            state["mode"] = "block"
            started.clear()
            release.clear()
            expected = 404 if action == "archive" else 409
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    request,
                    endpoint,
                    "POST",
                    item_path + "/diagnose",
                    token=token,
                    expected=expected,
                )
                try:
                    assert started.wait(10)
                    if action == "work":
                        request(
                            endpoint,
                            "POST",
                            item_path + "/student-work",
                            {"answer": "4", "steps": ["x=4"]},
                            token=token,
                        )
                    else:
                        request(endpoint, "DELETE", item_path, token=token)
                finally:
                    release.set()
                assert future.result() == expected
            state["mode"] = "good"
            assert (
                query(
                    env,
                    f"SELECT COUNT(*) FROM diagnoses WHERE question_id='{item['id']}'",
                )
                == "0"
            )
        # Cached and newly computed counterfactuals share a single evidence record.
        state["mode"] = "good"
        counter_item = create()
        counter_base = base(counter_item)
        counter_diagnosis = request(
            endpoint, "POST", counter_base + "/diagnose", token=token
        )
        counter_path = counter_base + "/diagnosis/counterfactual"
        request(endpoint, "POST", counter_path, expected=401)
        request(endpoint, "POST", counter_path, token=other, expected=404)
        missing = create()
        request(
            endpoint,
            "POST",
            base(missing) + "/diagnosis/counterfactual",
            token=token,
            expected=404,
        )
        calls_before = state["calls"]
        assert (
            request(endpoint, "POST", counter_path, token=token)
            == counter_diagnosis["counterfactual"]
        )
        assert state["calls"] == calls_before
        diagnosis_id = counter_diagnosis["id"]

        def remove_counter():
            query(
                env,
                f"DELETE FROM diagnosis_evidence WHERE diagnosis_id='{diagnosis_id}' AND kind='counterfactual_validation'",
            )

        def count_counter():
            return query(
                env,
                f"SELECT COUNT(*) FROM diagnosis_evidence WHERE diagnosis_id='{diagnosis_id}' AND kind='counterfactual_validation'",
            )

        remove_counter()
        query(
            env,
            f"ALTER TABLE diagnosis_evidence ADD CONSTRAINT counter_failure CHECK (diagnosis_id <> '{diagnosis_id}' OR kind <> 'counterfactual_validation')",
        )
        try:
            request(endpoint, "POST", counter_path, token=token, expected=503)
            assert count_counter() == "0"
        finally:
            query(env, "ALTER TABLE diagnosis_evidence DROP CHECK counter_failure")
        state["mode"] = "block"
        started.clear()
        release.clear()
        calls_before = state["calls"]
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(request, endpoint, "POST", counter_path, token=token)
                for _ in range(2)
            ]
            try:
                deadline = time.monotonic() + 10
                while state["calls"] < calls_before + 2:
                    assert time.monotonic() < deadline
                    time.sleep(0.05)
            finally:
                release.set()
            values = [future.result() for future in futures]
        assert values[0] == values[1] and values[0]["root_cause_confirmed"] is True
        assert count_counter() == "1"
        assert (
            query(
                env,
                f"SELECT COUNT(*) FROM diagnosis_evidence WHERE diagnosis_id='{diagnosis_id}' AND kind='step_alignment'",
            )
            == "2"
        )
        remove_counter()
        started.clear()
        release.clear()
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                request, endpoint, "POST", counter_path, token=token, expected=409
            )
            try:
                assert started.wait(10)
                request(
                    endpoint,
                    "PATCH",
                    counter_base + "/diagnosis",
                    {"root_misconception": "人工修正原因"},
                    token=token,
                )
            finally:
                release.set()
            assert future.result() == 409
        assert count_counter() == "0"
        state["mode"] = "good"
        request(endpoint, "POST", counter_path, token=token)
        assert count_counter() == "1"
        request(endpoint, "PATCH", counter_base + "/diagnosis",
                {"first_error_step": 1}, token=token)
        remove_counter()
        fresh = request(endpoint, "POST", counter_path, token=token)
        assert fresh["stale_after_correction"] and not fresh["root_cause_confirmed"]
        assert request(endpoint, "POST", counter_path, token=token) == fresh
        assert count_counter() == "1"
        request(endpoint, "DELETE", counter_base, token=token)
        request(endpoint, "POST", counter_path, token=token, expected=404)
        # Correction updates only the newest diagnosis and protects it from an in-flight model.
        state["mode"] = "good"
        item = create()
        item_path = base(item)
        first = request(endpoint, "POST", item_path + "/diagnose", token=token)
        current = request(endpoint, "POST", item_path + "/diagnose", token=token)
        correction_path = item_path + "/diagnosis"
        request(endpoint, "PATCH", correction_path, {}, expected=401)
        request(endpoint, "PATCH", correction_path, {}, token=other, expected=404)
        empty_item = create()
        request(
            endpoint,
            "PATCH",
            base(empty_item) + "/diagnosis",
            {},
            token=token,
            expected=404,
        )
        for invalid in (
            {"first_error_step": -1},
            {"first_error_step": 1.5},
            {"first_error_step": 2147483648},
            {"confidence": 1.1},
            {"confidence": "NaN"},
            {"error_type": "x" * 61},
            {"missing_prerequisites": [{}]},
        ):
            request(
                endpoint, "PATCH", correction_path, invalid, token=token, expected=422
            )
        corrected = request(
            endpoint,
            "PATCH",
            correction_path,
            {
                "first_error_step": None,
                "root_misconception": "人工核对后的原因",
                "confidence": "0.7",
                "missing_prerequisites": ["移项"],
                "question_id": q["id"],
                "user_confirmed": False,
            },
            token=token,
        )
        assert (
            corrected["id"] == current["id"] and corrected["question_id"] == item["id"]
        )
        assert (
            corrected["first_error_step"] is None
            and corrected["user_confirmed"] is True
        )
        assert corrected["root_misconception"] == "人工核对后的原因"
        assert corrected["correction"]["confidence"] == "0.7"
        assert (
            query(env, f"SELECT user_confirmed FROM diagnoses WHERE id='{first['id']}'")
            == "0"
        )
        assert (
            len(request(endpoint, "GET", correction_path, token=token)["evidence"]) == 2
        )
        query(
            env,
            "ALTER TABLE diagnoses ADD CONSTRAINT correction_failure CHECK (root_misconception <> 'rollback-correction')",
        )
        try:
            request(
                endpoint,
                "PATCH",
                correction_path,
                {"root_misconception": "rollback-correction", "confidence": 0.2},
                token=token,
                expected=503,
            )
            saved = request(endpoint, "GET", correction_path, token=token)
            assert saved["root_misconception"] == "人工核对后的原因"
            assert saved["correction"] == corrected["correction"]
        finally:
            query(env, "ALTER TABLE diagnoses DROP CHECK correction_failure")
        state["mode"] = "block"
        started.clear()
        release.clear()
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                request,
                endpoint,
                "POST",
                item_path + "/diagnose",
                token=token,
                expected=409,
            )
            try:
                assert started.wait(10)
                request(
                    endpoint,
                    "PATCH",
                    correction_path,
                    {"recommended_strategy": "按人工核对继续"},
                    token=token,
                )
            finally:
                release.set()
            assert future.result() == 409
        state["mode"] = "good"
        assert (
            request(endpoint, "GET", correction_path, token=token)[
                "recommended_strategy"
            ]
            == "按人工核对继续"
        )
        assert (
            query(
                env, f"SELECT COUNT(*) FROM diagnoses WHERE question_id='{item['id']}'"
            )
            == "2"
        )
        request(endpoint, "DELETE", item_path, token=token)
        request(endpoint, "PATCH", correction_path, {}, token=token, expected=409)
        failed = create()
        request(endpoint, "POST", base(failed) + "/analyze", token=token)
        for probability in (-0.1, 1.1):
            state["diagnosis_result"]["confidence"] = probability
            request(endpoint, "POST", base(failed) + "/diagnose", token=token, expected=503)
            assert query(env, f"SELECT COUNT(*) FROM diagnoses WHERE question_id='{failed['id']}'") == "0"
        state["diagnosis_result"]["confidence"] = 0.8
        state["mode"] = "fail"
        request(endpoint, "POST", base(failed) + "/diagnose", token=token, expected=503)
        assert (
            query(
                env,
                f"SELECT COUNT(*) FROM diagnoses WHERE question_id='{failed['id']}'",
            )
            == "0"
        )
    finally:
        release.set()
        state["mode"] = "good"
        state["diagnosing"] = False
    print(
        "Cangjie diagnosis passed: authorization, automatic analysis, evidence, knowledge upsert, latest history, rollback, answer-only and stale-input protection"
    )
