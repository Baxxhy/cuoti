"""Independent, persisted page-audit fixtures; analysis is controlled test data."""
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageDraw, ImageFont
from smoke_cangjie_accounts import request
from smoke_cangjie_detail import fixture_insert


def redesign_fixture(endpoint, env, query):
    email = f"routes-{uuid4().hex}@example.test"
    password = "RouteAudit-" + uuid4().hex
    actor = request(endpoint, "POST", "/api/v1/auth/register", {
        "email": email, "password": password, "name": "全站页面验收", "grade": "初一",
    })
    question = request(endpoint, "POST", "/api/v1/questions/manual", {
        "question_text": "解方程：2x+3=11", "student_answer": "x=7",
        "student_steps": ["2x=11+3", "x=7"], "subject": "数学", "grade": "初一",
    }, token=actor["access_token"])
    insert = fixture_insert(env, query)
    analysis = insert("problem_analyses", question_id=question["id"], subject="数学",
                      final_answer="x=4", verified=True, knowledge_points=["等式的性质"])
    insert("reference_steps", analysis_id=analysis, step_index=0, text="2x=8")
    insert("reference_steps", analysis_id=analysis, step_index=1, text="x=4")
    insert("diagnoses", question_id=question["id"], first_error_step=0,
           error_type="sign_error", root_misconception="移项需要改变符号")
    # A controlled illustration for the same equation, served through real media URLs.
    relative = Path("uploads") / "questions" / question["id"] / "route-figure.png"
    destination = Path(env["CANGJIE_MEDIA_ROOT"]) / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    picture = Image.new("RGB", (480, 150), "white")
    draw = ImageDraw.Draw(picture)
    font = ImageFont.load_default(size=24)
    draw.rounded_rectangle((20, 32, 198, 112), radius=8, outline="#002fa7", width=2)
    draw.rounded_rectangle((282, 32, 460, 112), radius=8, outline="#002fa7", width=2)
    draw.text((64, 56), "2x + 3", font=font, fill="#1d1d1f")
    draw.text((232, 56), "=", font=font, fill="#1d1d1f")
    draw.text((354, 56), "11", font=font, fill="#1d1d1f")
    picture.save(destination)
    insert("question_assets", question_id=question["id"], kind="question_figure",
           path=relative.as_posix(), sha256=sha256(destination.read_bytes()).hexdigest(),
           bbox=[0, 0, 1, 1], role="question", description="等式左右两边（隔离验收图示）")
    return {"QA_ROUTE_EMAIL": email, "QA_ROUTE_PASSWORD": password,
            "QA_ROUTE_QUESTION_ID": question["id"]}
