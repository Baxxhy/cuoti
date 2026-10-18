"""Exercise the detail response with independent, disposable MySQL fixtures."""

import hashlib
import hmac
import json
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit
from urllib.request import urlopen
from uuid import uuid4

from smoke_cangjie_accounts import request


def fixture_insert(env, query):
    defaults = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "backend-cangjie/tests/detail_defaults.json"
        ).read_text()
    )

    def insert(table, **fields):
        row = {
            **defaults[table],
            "id": str(uuid4()),
            "created_at": "2026-01-01 00:00:00",
            "updated_at": "2026-01-01 00:00:00",
            **fields,
        }

        def literal(value):
            if value is None:
                return "NULL"
            if isinstance(value, bool):
                return str(int(value))
            if isinstance(value, (int, float)):
                return str(value)
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            return (
                "CONVERT(0x" + value.encode().hex() + " USING utf8mb4)"
                if value
                else "''"
            )

        query(
            env,
            "INSERT INTO "
            + table
            + " ("
            + ",".join("`" + k + "`" for k in row)
            + ") VALUES ("
            + ",".join(literal(v) for v in row.values())
            + ")",
        )
        return row["id"]

    return insert


def detail(endpoint, env, token, question_id, query):
    path = "/api/v1/questions/" + question_id
    empty = request(endpoint, "GET", path, token=token)
    assert empty["confirmed"] is True and empty["favorite"] is False
    assert empty["question_text"] == "求解：x² = 4，说明解题步骤。"
    assert empty["analysis"] is None and empty["diagnosis"] is None
    assert empty["assets"] == [] and empty["ocr_runs"] == []
    assert empty["processing_job"] is None and empty["crop_box"] is None
    assert [s["step_index"] for s in empty["student_steps"]] == [0, 1]
    assert all(s["user_confirmed"] is True for s in empty["student_steps"])
    request(endpoint, "GET", path, expected=401)
    other = request(
        endpoint,
        "POST",
        "/api/v1/auth/register",
        {
            "email": f"detail-{uuid4().hex}@example.test",
            "password": "test-password-123",
            "name": "其他账号",
        },
    )
    request(endpoint, "GET", path, token=other["access_token"], expected=404)
    request(
        endpoint, "GET", "/api/v1/questions/" + str(uuid4()), token=token, expected=404
    )
    insert = fixture_insert(env, query)

    for kind in (
        "original",
        "crop",
        "question_figure",
        "student_working_figure",
        "teacher_annotation_region",
    ):
        insert(
            "question_assets",
            question_id=question_id,
            kind=kind,
            path=f"uploads/中文 空格/{kind}.png",
            bbox=[0.1, 0.2, 0.8, 0.9],
        )
    crop_ocr = insert(
        "ocr_runs", question_id=question_id, confidence=0.8, raw_result={"text": "中文"}
    )
    insert(
        "ocr_runs",
        question_id=question_id,
        stream="other",
        created_at="2026-01-02 00:00:00",
    )
    analysis = insert(
        "problem_analyses", question_id=question_id, subject="数学", verified=True
    )
    insert(
        "reference_steps",
        analysis_id=analysis,
        step_index=2,
        text="第二步",
        math_valid=True,
    )
    insert("reference_steps", analysis_id=analysis, step_index=1, text="第一步")
    insert("diagnoses", question_id=question_id, root_misconception="旧诊断")
    diagnosis = insert(
        "diagnoses",
        question_id=question_id,
        root_misconception="漏掉负根",
        first_error_step=1,
        created_at="2026-01-02 00:00:00",
    )
    insert(
        "diagnosis_evidence",
        diagnosis_id=diagnosis,
        kind="step_alignment",
        content="步骤证据",
        is_first_error=True,
    )
    insert(
        "diagnosis_evidence",
        diagnosis_id=diagnosis,
        kind="counterfactual_validation",
        content="反事实",
        metadata_json={"valid": True},
    )
    insert(
        "diagnosis_evidence",
        diagnosis_id=diagnosis,
        kind="other",
        content="不列入步骤证据",
    )
    insert(
        "teacher_marks", question_id=question_id, comment="注意负根", confidence=0.75
    )
    job = insert(
        "processing_jobs",
        question_id=question_id,
        kind="ocr",
        status="running",
        progress=45,
    )
    insert(
        "processing_jobs",
        question_id=question_id,
        kind="analyze",
        status="running",
        created_at="2026-01-03 00:00:00",
    )
    insert(
        "processing_jobs",
        question_id=question_id,
        kind="ocr",
        status="completed",
        created_at="2026-01-04 00:00:00",
    )
    data = request(endpoint, "GET", path, token=token)
    assert data["ocr"]["id"] == crop_ocr and len(data["ocr_runs"]) == 2
    assert abs(data["ocr"]["confidence"] - 0.8) < 1e-6
    assert data["analysis"]["verified"] is True
    assert [s["step_index"] for s in data["reference_steps"]] == [1, 2]
    assert data["diagnosis"]["id"] == diagnosis
    assert data["diagnosis"]["counterfactual"] == {"valid": True}
    assert len(data["diagnosis"]["evidence"]) == 1
    assert data["diagnosis"]["evidence"][0]["is_first_error"] is True
    assert data["teacher_marks"][0]["comment"] == "注意负根"
    assert (
        data["processing_job"]["id"] == job and data["processing_job"]["progress"] == 45
    )
    job_path = "/api/v1/jobs/" + job
    polled = request(endpoint, "GET", job_path, token=token)
    assert polled["id"] == job and polled["progress"] == 45 and polled["error"] is None
    request(endpoint, "GET", job_path, expected=401)
    request(endpoint, "GET", job_path, token=other["access_token"], expected=404)
    request(endpoint, "GET", "/api/v1/jobs/" + str(uuid4()), token=token, expected=404)
    request(endpoint, "POST", job_path, token=token, expected=405)
    assert all(
        abs(a - b) < 1e-6
        for a, b in zip(data["crop_box"], [0.1, 0.2, 0.7, 0.7], strict=True)
    )
    for group in (
        "question_figures",
        "student_working_figures",
        "teacher_annotation_regions",
    ):
        assert len(data[group]) == 1
    for asset in data["assets"]:
        url = urlsplit(asset["url"])
        params = parse_qs(url.query)
        signed = f"media:v1:{params['expires'][0]}:{unquote(url.path)}"
        expected = hmac.new(
            env["CANGJIE_AUTH_SECRET"].encode(), signed.encode(), hashlib.sha256
        ).hexdigest()
        assert params["signature"] == [expected]
        assert unquote(url.path) == "/" + asset["path"]
        local = Path(env["CANGJIE_MEDIA_ROOT"]) / asset["path"]
        local.parent.mkdir(parents=True, exist_ok=True)
        payload = ("真实资源读取：" + asset["kind"]).encode()
        local.write_bytes(payload)
        with urlopen(endpoint + asset["url"], timeout=10) as response:
            assert response.status == 200 and response.read() == payload
    query(
        env,
        f"UPDATE question_assets SET bbox=JSON_ARRAY(0.8,0.2,0.1,0.9) WHERE question_id='{question_id}' AND kind='crop'",
    )
    assert request(endpoint, "GET", path, token=token)["crop_box"] is None
    print(
        "Cangjie detail passed: typed fields, ownership, OCR preference, evidence, ordered steps, jobs, crop and signed URLs"
    )
