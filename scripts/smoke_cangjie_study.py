"""Public-bank practice and timed exams: native ownership, snapshots, answers, grading, deadlines."""

import json
import subprocess
from pathlib import Path
from uuid import uuid4

from smoke_cangjie_accounts import request
from smoke_cangjie_detail import fixture_insert


def study(endpoint, env, query):
    assert env["CANGJIE_DB_NAME"].startswith("zhiwei_cangjie_test")
    insert = fixture_insert(env, query)
    source = insert("dataset_sources", key="study-" + uuid4().hex, name="练习验收题库")
    ids = []
    for number in range(1, 7):
        ids.append(
            insert(
                "dataset_questions",
                dataset_source_id=source,
                source_item_id=str(number),
                content_hash=uuid4().hex,
                subject="数学",
                grade="初一",
                grade_band="初中",
                question_text=f"计算：{number}+1等于多少？",
                question_type="multiple-choice",
                options=[
                    {"key": "A", "text": str(number + 1)},
                    {"key": "B", "text": str(number + 2)},
                ],
                answer=json.dumps("A"),
                solution=f"{number}+1={number + 1}",
                image_paths=[],
                has_answer=True,
                usable_for_practice=True,
                usable_for_auto_grade=True,
            )
        )
    insert(
        "dataset_questions",
        dataset_source_id=source,
        source_item_id="disabled",
        subject="数学",
        grade_band="初中",
        question_text="不可练题目",
        content_hash=uuid4().hex,
        usable_for_practice=False,
        usable_for_auto_grade=False,
    )
    email = "study-browser-" + uuid4().hex + "@example.test"
    password = "StudyBrowser-12345"
    actor = request(
        endpoint,
        "POST",
        "/api/v1/auth/register",
        {"email": email, "password": password, "name": "题库验收学生", "grade": "初一"},
    )
    other = request(
        endpoint,
        "POST",
        "/api/v1/auth/register",
        {
            "email": "study-other-" + uuid4().hex + "@example.test",
            "password": password,
            "name": "其他学生",
        },
    )
    token = actor["access_token"]
    foreign = other["access_token"]
    request(endpoint, "GET", "/api/v1/study-bank", expected=401)
    bank = request(
        endpoint, "GET", "/api/v1/study-bank?source_id=" + source, token=token
    )
    assert bank["total"] == 6 and len(bank["questions"]) == 6
    assert all(
        "answer" not in q and "solution" not in q and "source_metadata" not in q
        for q in bank["questions"]
    )
    assert all(q["source_name"] == "练习验收题库" for q in bank["questions"])
    filtered = request(
        endpoint,
        "GET",
        "/api/v1/study-bank?source_id=" + source + "&search=1%2B1",
        token=token,
    )
    assert filtered["total"] == 1 and filtered["questions"][0]["id"] == ids[0]
    empty = request(
        endpoint,
        "GET",
        "/api/v1/study-bank?source_id=" + source + "&grade_band=missing",
        token=token,
    )
    assert empty["total"] == 0 and empty["questions"] == []
    request(endpoint, "GET", "/api/v1/study-bank?page=0", token=token, expected=422)
    request(
        endpoint, "GET", "/api/v1/study-bank?subject=%27%20OR%201%3D1--", token=token
    )
    for payload in [
        {"count": 0},
        {"count": 21},
        {"count": True},
        {"minutes": 0},
        {"mode": "fake"},
        {"question_ids": "wrong"},
        {"question_ids": [ids[0], ids[1]]},
    ]:
        request(
            endpoint,
            "POST",
            "/api/v1/study-sessions",
            payload,
            token=token,
            expected=422,
        )
    session = request(
        endpoint,
        "POST",
        "/api/v1/study-sessions",
        {
            "mode": "practice",
            "source_id": source,
            "subject": "数学",
            "grade_band": "初中",
            "search": "1+1",
            "count": 1,
        },
        token=token,
    )
    assert session["items"][0]["question"]["id"] == ids[0]
    path = "/api/v1/study-sessions/" + session["id"]
    assert (
        session["question_count"] == 1
        and session["status"] == "active"
        and session["items"][0]["student_answer"] is None
    )
    assert (
        "answer" not in session["items"][0]
        and "answer" not in session["items"][0]["question"]
    )
    request(endpoint, "GET", path, token=foreign, expected=404)
    request(
        endpoint,
        "PATCH",
        path,
        {"version": 1, "answers": []},
        token=foreign,
        expected=404,
    )
    request(
        endpoint, "POST", path + "/submit", {"version": 1}, token=foreign, expected=404
    )
    item = session["items"][0]["id"]
    request(
        endpoint,
        "PATCH",
        path,
        {"version": 1, "answers": [{"id": "forged", "answer": ["A"]}]},
        token=token,
        expected=422,
    )
    saved = request(
        endpoint,
        "PATCH",
        path,
        {"version": 1, "answers": [{"id": item, "answer": ["A"]}]},
        token=token,
    )
    assert saved["version"] == 2 and saved["items"][0]["student_answer"] == ["A"]
    request(
        endpoint,
        "PATCH",
        path,
        {"version": 1, "answers": [{"id": item, "answer": ["B"]}]},
        token=token,
        expected=409,
    )
    assert request(endpoint, "GET", path, token=token)["items"][0][
        "student_answer"
    ] == ["A"]
    # The session retains the question served, even if the public bank changes.
    query(
        env,
        f"UPDATE dataset_questions SET answer=JSON_QUOTE('B'),question_text='已更新的题目' WHERE id='{ids[0]}'",
    )
    result = request(endpoint, "POST", path + "/submit", {"version": 2}, token=token)
    assert result["status"] == "submitted" and result["results"] == {
        "correct": 1,
        "pending": 0,
        "answered": 1,
        "total": 1,
        "score": 5,
        "max_score": 5,
    }
    assert (
        result["items"][0]["answer"] == "A"
        and "计算" in result["items"][0]["question"]["question_text"]
    )
    again = request(endpoint, "POST", path + "/submit", {"version": 1}, token=token)
    assert (
        again["version"] == result["version"] and again["results"] == result["results"]
    )
    request(
        endpoint,
        "PATCH",
        path,
        {"version": result["version"], "answers": [{"id": item, "answer": ["B"]}]},
        token=token,
        expected=409,
    )
    query(
        env, f"UPDATE dataset_questions SET answer=JSON_QUOTE('A') WHERE id='{ids[0]}'"
    )
    exam = request(
        endpoint,
        "POST",
        "/api/v1/study-sessions",
        {
            "mode": "exam",
            "source_id": source,
            "subject": "数学",
            "count": 5,
            "minutes": 10,
        },
        token=token,
    )
    assert exam["question_count"] == 5 and 0 < exam["remaining_seconds"] <= 600
    assert len({q["question"]["id"] for q in exam["items"]}) == 5
    exam_path = "/api/v1/study-sessions/" + exam["id"]
    payload = {
        "version": 1,
        "answers": [{"id": q["id"], "answer": ["A"]} for q in exam["items"]],
    }
    saved = request(endpoint, "PATCH", exam_path, payload, token=token)
    resumed = request(endpoint, "GET", exam_path, token=token)
    assert (
        all(q["student_answer"] == ["A"] for q in resumed["items"])
        and resumed["remaining_seconds"] <= 600
    )
    query(
        env,
        f"UPDATE study_sessions SET deadline_at=UTC_TIMESTAMP(6)-INTERVAL 1 SECOND WHERE id='{exam['id']}'",
    )
    assert request(endpoint, "GET", exam_path, token=token)["expired"] == 1
    payload["version"] = saved["version"]
    request(endpoint, "PATCH", exam_path, payload, token=token, expected=409)
    result = request(
        endpoint,
        "POST",
        exam_path + "/submit",
        {"version": saved["version"]},
        token=token,
    )
    assert result["results"]["correct"] == 5 and result["results"]["score"] == 25
    blank = request(
        endpoint,
        "POST",
        "/api/v1/study-sessions",
        {"mode": "practice", "question_ids": [ids[1]]},
        token=token,
    )
    result = request(
        endpoint,
        "POST",
        "/api/v1/study-sessions/" + blank["id"] + "/submit",
        {"version": 1},
        token=token,
    )
    assert (
        result["results"]["score"] == 0
        and result["results"]["answered"] == 0
        and result["results"]["pending"] == 0
    )
    assert len(request(endpoint, "GET", "/api/v1/study-sessions", token=token)) == 3
    assert request(endpoint, "GET", "/api/v1/study-sessions", token=foreign) == []
    assert (
        query(env, f"SELECT COUNT(*) FROM mastery_states WHERE user_id='{actor['id']}'")
        == "0"
    )
    assert (
        query(env, f"SELECT COUNT(*) FROM questions WHERE user_id='{actor['id']}'")
        == "0"
    )
    print(
        "Study bank passed: real sources/filtering, hidden answers, owner isolation, validation, durable drafts/CAS, frozen snapshots, idempotent grading, server deadlines, empty answers and no fabricated mastery",
        flush=True,
    )
    chemical_source = insert(
        "dataset_sources", key="study-chemical-" + uuid4().hex, name="化学排版验收题库"
    )
    insert(
        "dataset_questions",
        dataset_source_id=chemical_source,
        source_item_id="hydrate",
        content_hash=uuid4().hex,
        subject="化学",
        grade="高二",
        grade_band="高中",
        question_text=r"胆矾\mathrm{CuSO_{4}5H_{2}O}可写作$${[Cu(H_{2}O)_{4}]SO_{4}H_{2}O}$$，下列说法正确的是",
        question_type="multiple-choice",
        options=[
            {"key": "A", "text": r"所有氧原子都采取$${sp^{3}}$$杂化"},
            {"key": "B", "text": "氧原子存在配位键和氢键两种化学键"},
            {"key": "C", "text": r"$${Cu^{2+}}$$的价电子排布式为$${3d^{8}4s^{1}}$$"},
            {"key": "D", "text": "胆矾中的水在不同温度下会分步失去"},
        ],
        answer=json.dumps("D"),
        solution=r"水分步失去。独立公式：\[Cu^{2+}\]",
        has_answer=True,
        usable_for_practice=True,
        usable_for_auto_grade=True,
    )
    blocked_source = insert("dataset_sources", key="format-" + uuid4().hex, name="不向学生显示的数据集")
    blocked_id = insert(
        "dataset_questions", dataset_source_id=blocked_source, source_item_id="broken",
        content_hash="d" * 64, subject="数学", grade="初一", grade_band="初中",
        question_text=r"不应展示的坏公式 $$\overset{⇌}$$", question_type="multiple-choice",
        options=[{"key": "A", "text": "甲"}, {"key": "B", "text": "乙"}],
        answer=json.dumps("A"), has_answer=True, usable_for_practice=True, usable_for_auto_grade=True,
    )
    held = request(endpoint, "POST", "/api/v1/study-sessions", {"mode": "practice", "question_ids": [blocked_id]}, token=token)
    to_submit = request(endpoint, "POST", "/api/v1/study-sessions", {"mode": "practice", "question_ids": [blocked_id]}, token=token)
    done = subprocess.run(
        ["bash", "scripts/cangjie.sh", "question-bank-built"],
        input=json.dumps({"operation": "review-format", "questions": [{"id": blocked_id, "content_hash": "d" * 64, "fields": ["question"]}]}) + "\n",
        cwd=Path(__file__).resolve().parents[1], env=env, text=True, capture_output=True, check=True,
    )
    assert json.loads(done.stdout)["changed"] == 1
    masked = request(endpoint, "GET", "/api/v1/study-sessions/" + held["id"], token=token)
    assert masked["items"][0]["unavailable"] is True
    assert "question_text" not in masked["items"][0]["question"]
    assert request(endpoint, "GET", "/api/v1/study-bank?source_id=" + blocked_source, token=token)["total"] == 0
    request(endpoint, "POST", "/api/v1/study-sessions", {"question_ids": [blocked_id]}, token=token, expected=422)
    request(endpoint, "POST", "/api/v1/study-sessions", {"mode": "exam", "source_id": blocked_source, "count": 1}, token=token, expected=422)
    excluded = request(endpoint, "POST", "/api/v1/study-sessions/" + to_submit["id"] + "/submit", {"version": to_submit["version"]}, token=token)
    assert excluded["results"]["excluded"] == 1
    assert excluded["results"]["pending"] == 0 and excluded["results"]["max_score"] == 0
    assert excluded["items"][0]["grading"]["method"] == "question_unavailable"
    assert "answer" not in excluded["items"][0] and "solution" not in excluded["items"][0]
    repeated = request(endpoint, "POST", "/api/v1/study-sessions/" + to_submit["id"] + "/submit", {"version": to_submit["version"]}, token=token)
    assert repeated["results"] == excluded["results"]
    # Fixing the current source must not make a frozen damaged version readable.
    history = json.dumps({"format_review_history": [{"content_hash": "d" * 64, "fields": ["question"]}]})
    query(env, "UPDATE dataset_questions SET content_hash='" + "e" * 64 + "',quality_status='usable',usable_for_practice=1,usable_for_auto_grade=1,question_text='修正后的题目',source_metadata='" + history + "' WHERE id='" + blocked_id + "'")
    still_blocked = request(endpoint, "GET", "/api/v1/study-sessions/" + held["id"], token=token)
    assert still_blocked["items"][0]["unavailable"] is True
    fresh = request(endpoint, "POST", "/api/v1/study-sessions", {"question_ids": [blocked_id]}, token=token)
    assert fresh["items"][0]["unavailable"] is False
    assert fresh["items"][0]["question"]["question_text"] == "修正后的题目"
    adaptive = request(endpoint, "POST", "/api/v1/study-sessions", {"mode": "practice", "source_id": source, "count": 3, "selection_strategy": "adaptive"}, token=token)
    chosen = [item["question"]["id"] for item in adaptive["items"]]
    assert len(chosen) == len(set(chosen)) == 3 and set(chosen).issubset(set(ids))
    assert all("answer" not in item and "adaptive_selection" not in item["question"] for item in adaptive["items"])
    traces = json.loads(query(env, f"SELECT JSON_ARRAYAGG(JSON_EXTRACT(snapshot,'$.adaptive_selection')) FROM study_session_items WHERE session_id='{adaptive['id']}'"))
    assert all(trace["strategy"] == "bkt_information_gain_v1" for trace in traces)
    assert all(trace["calibration"] == "cold_start_defaults" for trace in traces)
    assert any(point["evidence_count"] > 0 for trace in traces for point in trace["trace"])
    request(endpoint, "GET", "/api/v1/study-sessions/" + adaptive["id"], token=foreign, expected=404)
    request(endpoint, "POST", "/api/v1/study-sessions", {"selection_strategy": "unknown"}, token=token, expected=422)
    print("Adaptive practice passed: native owner history, bounded candidate pool, Bayesian information-gain selection, hidden answers and persisted trace", flush=True)
    print("Format quarantine passed: no new practice/exam, masked old snapshots, excluded scoring and idempotent submission", flush=True)
    # Junior students keep exact grades; senior students share the entire high-school band.
    grade_source = insert("dataset_sources", key="grade-" + uuid4().hex, name="年级隔离验收")
    grade_ids = {}
    for grade in ["七年级", "八年级", "九年级", "高一", "高二", "高三", "初中", "高中", "小学", "拓展"]:
        grade_ids[grade] = insert(
            "dataset_questions", dataset_source_id=grade_source, source_item_id=grade,
            content_hash=uuid4().hex, subject="数学", grade=grade,
            grade_band="高中" if grade.startswith("高") else "初中" if grade in ["七年级", "八年级", "九年级", "初中"] else grade,
            question_text="计算1+1", question_type="single-choice",
            options=[{"key": "A", "text": "2"}, {"key": "B", "text": "3"}],
            answer=json.dumps("A"), has_answer=True, usable_for_practice=True, usable_for_auto_grade=True,
        )
    for grade, text in [("七年级", "复数的虚部是什么"), ("八年级", "解一元二次方程"), ("九年级", "求向量的模"), ("高一", "求函数的导数"), ("高二", "求矩阵的特征值"), ("高三", "求不定积分")]:
        grade_ids["mislabelled-" + grade] = insert(
            "dataset_questions", dataset_source_id=grade_source, source_item_id="bad-" + grade,
            content_hash=uuid4().hex, subject="数学", grade=grade, grade_band="高中" if grade.startswith("高") else "初中",
            question_text=text, question_type="single-choice", options=[{"key": "A", "text": "2"}],
            answer=json.dumps("A"), has_answer=True, usable_for_practice=True, usable_for_auto_grade=True,
        )
    for grade, stored in [("初一", "七年级"), ("初二", "八年级"), ("初三", "九年级"), ("高一", "高一"), ("高二", "高二"), ("高三", "高三")]:
        pupil = request(endpoint, "POST", "/api/v1/auth/register", {
            "email": "grade-" + uuid4().hex + "@example.test", "password": password, "name": "年级验收", "grade": grade,
        })
        pupil_token = pupil["access_token"]
        result = request(endpoint, "GET", "/api/v1/study-bank?source_id=" + grade_source + "&grade=%E9%AB%98%E4%B8%89", token=pupil_token)
        allowed = {value for key, value in grade_ids.items() if key.startswith(("高", "mislabelled-高"))} if grade.startswith("高") else {grade_ids[stored]}
        assert result["grade"] == grade and result["total"] == len(allowed)
        assert {q["id"] for q in result["questions"]} == allowed
        assert result["scope_label"] == ("高中" if grade.startswith("高") else grade)
        assert sum(f["count"] for f in result["facets"]) >= 1
        for mode, strategy in [("practice", "random"), ("practice", "adaptive"), ("exam", "random")]:
            session = request(endpoint, "POST", "/api/v1/study-sessions", {
                "mode": mode, "selection_strategy": strategy, "source_id": grade_source, "count": len(allowed), "grade": "高三",
            }, token=pupil_token)
            assert {item["question"]["id"] for item in session["items"]} == allowed
        for excluded, excluded_id in grade_ids.items():
            if excluded_id not in allowed:
                request(endpoint, "POST", "/api/v1/study-sessions", {"question_ids": [excluded_id]}, token=pupil_token, expected=422)
        request(endpoint, "POST", "/api/v1/study-sessions", {"source_id": grade_source, "count": len(allowed) + 1}, token=pupil_token, expected=422)
    print("School scopes passed: junior exact grades, senior all high-school grades, random/adaptive/exam, foreign-band IDs and insufficient counts", flush=True)
    shuffle_source = insert("dataset_sources", key="shuffle-" + uuid4().hex, name="随机混排验收")
    for subject in ["数学", "英语", "化学"]:
        for position in range(25):
            insert("dataset_questions", dataset_source_id=shuffle_source,
                   source_item_id=subject + str(position), content_hash=uuid4().hex,
                   subject=subject, grade="高中", grade_band="高中",
                   question_text="随机混排样本" + str(position), question_type="single-choice",
                   options=[{"key": "A", "text": "选项"}], answer=json.dumps("A"),
                   has_answer=True, usable_for_practice=True, usable_for_auto_grade=True)
    def shuffled(seed, page=1):
        return request(endpoint, "GET", f"/api/v1/study-bank?source_id={shuffle_source}&shuffle_seed={seed}&page={page}", token=pupil_token)["questions"]
    first, second = shuffled(17), shuffled(17, 2)
    assert len(first) == len(second) == 20
    assert {q["subject"] for q in first} == {"数学", "英语", "化学"}
    assert max(sum(q["subject"] == subject for q in first) for subject in ["数学", "英语", "化学"]) == 7
    assert [q["id"] for q in first] == [q["id"] for q in shuffled(17)]
    assert not ({q["id"] for q in first} & {q["id"] for q in second})
    assert [q["id"] for q in first] != [q["id"] for q in shuffled(29)]
    request(endpoint, "GET", "/api/v1/study-bank?shuffle_seed=invalid", token=pupil_token, expected=422)
    print("Random mixed bank passed: balanced subjects, repeatable seed, disjoint pagination and reshuffle", flush=True)
    # Figures from OCR sources are interleaved with question/options/solutions.
    # Keep a real, signed PNG for each role and verify the pre-submit boundary.
    from PIL import Image, ImageDraw

    figure_source = insert("dataset_sources", key="figure-layout-" + uuid4().hex, name="图片排版验收")
    image_root = Path(env["CANGJIE_QUESTION_BANK_ROOT"])
    image_root.mkdir(parents=True, exist_ok=True)
    figure_paths = []
    for index, label in enumerate(["QUESTION", "OPTION A", "SOLUTION 1", "SOLUTION 2"]):
        file = image_root / f"figure-layout-{index}.png"
        picture = Image.new("RGB", (180, 100), "#eff4fd")
        ImageDraw.Draw(picture).text((12, 40), label, fill="#30343c")
        picture.save(file)
        figure_paths.append(str(file))
    figure_id = insert(
        "dataset_questions", dataset_source_id=figure_source, source_item_id="figure-layout",
        content_hash="f" * 64, subject="数学", grade="初一", grade_band="初中",
        question_text="如图，计算 $1+1$。<ImageHere>选择正确的选项图。", question_type="single-choice",
        options=[{"key": "A", "text": "<ImageHere>"}, {"key": "B", "text": "3"}],
        answer=json.dumps("A"), solution="第一步<ImageHere>第二步<ImageHere>",
        image_paths=figure_paths, source_metadata={"has_visual": True},
        has_answer=True, usable_for_practice=True, usable_for_auto_grade=True,
    )
    public = request(endpoint, "GET", "/api/v1/study-bank?source_id=" + figure_source, token=token)["questions"][0]
    assert len(public["image_urls"]) == 1 and len(public["options"][0]["image_urls"]) == 1
    assert len(public["preview_image_urls"]) == 2
    assert "/images/2" not in json.dumps(public) and "/images/3" not in json.dumps(public)
    figure_session = request(endpoint, "POST", "/api/v1/study-sessions", {"question_ids": [figure_id]}, token=token)
    item_id = figure_session["items"][0]["id"]
    saved = request(endpoint, "PATCH", "/api/v1/study-sessions/" + figure_session["id"], {"version": figure_session["version"], "answers": [{"id": item_id, "answer": ["A"]}]}, token=token)
    graded = request(endpoint, "POST", "/api/v1/study-sessions/" + figure_session["id"] + "/submit", {"version": saved["version"]}, token=token)
    assert len(graded["items"][0]["solution_image_urls"]) == 2
    print("Dataset figures passed: stem/option images are public; solution figures appear only after submission", flush=True)
    return {
        "QA_STUDY_FIGURE_SOURCE": figure_source,
        "QA_STUDY_CHEM_SOURCE": chemical_source,
        "QA_STUDY_BLOCKED_SESSION": held["id"],
        "QA_STUDY_EMAIL": email,
        "QA_STUDY_PASSWORD": password,
        "QA_STUDY_SOURCE": source,
    }
