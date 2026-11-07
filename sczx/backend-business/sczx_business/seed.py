import os

from sqlalchemy import select

from .database import Base, SessionLocal, engine
from .models import Account, ClassMember, Classroom, Course, Lesson, LessonDraft, SupportIssue, TeachingCase
from .security import hash_password


BLOCKS = [
    {"id": "observe", "title": "从天平开始观察", "content": "展示保持平衡的天平。请学生预测：如果两边同时增加相同数量的砝码，天平会怎样变化？先说出理由，再实际操作。"},
    {"id": "express", "title": "把观察写成等式", "content": "把两边同时增加的过程写下来。引导学生用“同时”和“相同”解释等式性质，比较只改变一边的情况。"},
    {"id": "practice", "title": "在新题中独立应用", "content": "给出 x − 3 = 5，请学生解释两边的运算。需要帮助时提供提示，再用 y + 4 = 11 检查能否独立完成。"},
]
QUESTIONS = [
    {"equation": "x − 3 = 5", "prompt": "等式两边同时加上 3，x 等于多少？", "answer": "8", "hint": "左边的 −3 与 +3 抵消。右边也要加上 3。"},
    {"equation": "y + 4 = 11", "prompt": "等式两边同时减去 4，y 等于多少？", "answer": "7", "hint": "在左右两边同时减去 4，右边变为 11 − 4。"},
]
CASE_TEXT = "先预测，再操作，最后解释。根据学生回应调整讲法，将“同时”和“相同”落实到每一步。"


def ensure_seed() -> None:
    Base.metadata.create_all(engine)
    accounts = [
        (os.getenv("SCZX_BOOTSTRAP_ADMIN_USERNAME", "admin"), os.getenv("SCZX_BOOTSTRAP_ADMIN_PASSWORD", ""), "管理员", "admin"),
        (os.getenv("SCZX_BOOTSTRAP_TEACHER_USERNAME", "teacher"), os.getenv("SCZX_BOOTSTRAP_TEACHER_PASSWORD", ""), "演示教师", "teacher"),
        (os.getenv("SCZX_BOOTSTRAP_STUDENT_USERNAME", "student"), os.getenv("SCZX_BOOTSTRAP_STUDENT_PASSWORD", ""), "演示学生", "student"),
    ]
    with SessionLocal.begin() as db:
        for username, password, display_name, role in accounts:
            if not password:
                continue
            if db.scalar(select(Account).where(Account.username == username)):
                continue
            db.add(Account(id=f"account-{role}-demo", username=username, display_name=display_name, role=role, password_hash=hash_password(password)))
        if not db.get(Course, "course-equation"):
            db.add(Course(id="course-equation", title="一元一次方程", grade="七年级数学"))
            db.add(Lesson(id="lesson-equation", course_id="course-equation", title="等式性质", position=1))
        if not db.get(TeachingCase, "case-balance"):
            db.add(TeachingCase(id="case-balance", title="天平与等式性质", source="待补充核对的教学示例", content=CASE_TEXT, status="published"))
        admin = db.scalar(select(Account).where(Account.role == "admin").order_by(Account.created_at).limit(1))
        teacher = db.scalar(select(Account).where(Account.role == "teacher").order_by(Account.created_at).limit(1))
        student = db.scalar(select(Account).where(Account.role == "student").order_by(Account.created_at).limit(1))
        if teacher and student:
            classroom = db.get(Classroom, "class-demo")
            if not classroom:
                db.add(Classroom(id="class-demo", teacher_id=teacher.id, name="七年级一班", grade="七年级数学"))
            if not db.get(ClassMember, {"classroom_id": "class-demo", "student_id": student.id}):
                db.add(ClassMember(classroom_id="class-demo", student_id=student.id))
            if not db.scalar(select(LessonDraft).where(LessonDraft.teacher_id == teacher.id)):
                db.add(LessonDraft(id="draft-equation", teacher_id=teacher.id, lesson_id="lesson-equation", case_id="case-balance", goal="理解并应用等式两边的共同变化", student_base="已理解相等关系，容易机械记忆移项变号", due_date="2026-11-14", blocks=BLOCKS, questions=QUESTIONS))
            if not db.scalar(select(SupportIssue).where(SupportIssue.owner_id == student.id)):
                db.add(SupportIssue(id="issue-demo", owner_id=student.id, text="为什么只改变一边，等式就不成立了？"))
