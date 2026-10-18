#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.auth import hash_password
from app.db import SessionLocal
from app.models import (
    Diagnosis,
    GuardianStudentLink,
    MasteryState,
    MisconceptionState,
    ProblemAnalysis,
    Question,
    ReferenceStep,
    ReviewPlan,
    StudentProfile,
    StudentStep,
    StudentWork,
    TeacherClass,
    TeacherClassStudent,
    User,
)

DEMO_STUDENT_EMAIL = "e2e@minddimension.local"

STUDENTS = [
    (DEMO_STUDENT_EMAIL, "演示学生", "数学", "一元一次方程", "移项符号错误", 0.62),
    ("lin@minddimension.local", "林晓", "物理", "匀速直线运动", "速度与路程公式混淆", 0.71),
    ("chen@minddimension.local", "陈一", "数学", "勾股定理", "斜边识别错误", 0.55),
    ("zhou@minddimension.local", "周可", "历史", "历史时间线", "因果层级混淆", 0.78),
    ("sun@minddimension.local", "孙宁", "物理", "受力分析", "漏画支持力", 0.48),
]


async def one(db, model, *criteria):
    return (await db.scalars(select(model).where(*criteria))).first()


async def ensure_user(db, email: str, name: str, role: str, password: str = "123456") -> User:
    user = await one(db, User, User.email == email)
    if user is None:
        user = User(email=email, name=name, role=role, password_hash=hash_password(password)); db.add(user); await db.flush()
    else:
        user.name, user.role, user.password_hash = name, role, hash_password(password)
    return user


async def ensure_student_data(
    db, student: User, subject: str, knowledge: str, misconception: str, mastery_score: float,
) -> None:
    if await one(db, StudentProfile, StudentProfile.user_id == student.id) is None:
        db.add(StudentProfile(user_id=student.id, grade="初二", learning_goal=f"掌握{knowledge}"))
    mastery = await one(db, MasteryState, MasteryState.user_id == student.id,
                        MasteryState.subject == subject,
                        MasteryState.knowledge_point == knowledge)
    if mastery is None:
        db.add(MasteryState(user_id=student.id, subject=subject, knowledge_point=knowledge, mastery_score=mastery_score,
                            confidence=0.7, evidence_count=2, update_reason="演示学习证据"))
    code = "demo_" + student.email.split("@")[0]
    mistake = await one(db, MisconceptionState, MisconceptionState.user_id == student.id,
                        MisconceptionState.subject == subject,
                        MisconceptionState.code == code)
    if mistake is None:
        db.add(MisconceptionState(user_id=student.id, subject=subject, code=code, label=misconception,
                                  probability=round(1 - mastery_score / 2, 2), evidence_count=2))
    question = await one(db, Question, Question.user_id == student.id, Question.title == f"{knowledge}诊断题")
    if question is None:
        texts = {
            "一元一次方程": ("解方程：2x + 3 = 11", "x=7", "x=4"),
            "匀速直线运动": ("汽车以5m/s行驶6s，路程是多少？", "30m/s", "30m"),
            "勾股定理": ("直角边为3和4，求斜边。", "7", "5"),
            "历史时间线": ("将工业革命与法国大革命按时间排序并说明联系。", "工业革命在后", "工业革命先开始"),
            "受力分析": ("画出水平桌面上静止木块的受力。", "只有重力", "重力与支持力"),
        }
        text, student_answer, answer = texts[knowledge]
        question = Question(user_id=student.id, subject=subject, grade="初二", title=f"{knowledge}诊断题",
                            question_text=text, student_answer=student_answer, status="diagnosed",
                            confirmed=True, knowledge_points=[knowledge], question_type="诊断题")
        db.add(question); await db.flush()
        work = StudentWork(question_id=question.id, user_id=student.id, answer=student_answer)
        db.add(work); await db.flush()
        db.add(StudentStep(work_id=work.id, step_index=0, text=student_answer,
                           raw_text=student_answer, normalized_text=student_answer, user_confirmed=True))
        analysis = ProblemAnalysis(question_id=question.id, subject=subject, problem_type="诊断题",
                                   known_conditions=[text], goal="得到正确结论", knowledge_points=[knowledge],
                                   prerequisites=[], final_answer=answer, verified=True)
        db.add(analysis); await db.flush()
        db.add(ReferenceStep(analysis_id=analysis.id, step_index=0, text=answer,
                             explanation=f"应用{knowledge}并检查条件", math_valid=True))
        db.add(ReviewPlan(user_id=student.id, question_id=question.id,
                          due_at=datetime.now(timezone.utc) + timedelta(days=1), interval_days=1,
                          reason="演示错因需次日复习"))


async def ensure_geometry_demo(db, student: User) -> Question:
    """Give the default student a deterministic question for the geometry visual demo."""
    title = "互动演示：勾股定理"
    question = await one(db, Question, Question.user_id == student.id, Question.title == title)
    if question is not None:
        return question

    question = Question(
        user_id=student.id,
        subject="数学",
        grade="初二",
        title=title,
        question_text="在直角三角形ABC中，∠C=90°，AC=3 cm，BC=4 cm，求斜边AB的长度。",
        student_answer="AB=3+4=7 cm",
        status="diagnosed",
        confirmed=True,
        favorite=True,
        tags=["互动演示", "几何图"],
        formulas=["AB²=AC²+BC²"],
        knowledge_points=["勾股定理", "直角三角形"],
        question_type="几何计算题",
    )
    db.add(question); await db.flush()

    work = StudentWork(
        question_id=question.id,
        user_id=student.id,
        answer=question.student_answer,
        explanation="把两条直角边直接相加作为斜边。",
    )
    db.add(work); await db.flush()
    wrong_step = StudentStep(
        work_id=work.id,
        step_index=0,
        text="AB=AC+BC=3+4=7 cm",
        raw_text="AB=3+4=7",
        normalized_text="AB=7",
        formula="AB=AC+BC=7",
        confidence=1.0,
        source="demo",
        user_confirmed=True,
    )
    db.add(wrong_step); await db.flush()

    analysis = ProblemAnalysis(
        question_id=question.id,
        subject="数学",
        problem_type="几何计算题",
        known_conditions=["∠C=90°", "AC=3 cm", "BC=4 cm"],
        goal="求斜边AB的长度",
        knowledge_points=["勾股定理", "直角三角形"],
        prerequisites=["平方", "算术平方根"],
        final_answer="AB=5 cm",
        verified=True,
        raw_result={"visualization_type": "right_triangle", "demo": True},
    )
    db.add(analysis); await db.flush()
    reference_texts = [
        ("因为∠C=90°，所以AB是斜边。", "先确认斜边与两条直角边。"),
        ("AB²=AC²+BC²=3²+4²=25。", "使用勾股定理计算斜边的平方。"),
        ("AB=√25=5 cm。", "长度取正值。"),
    ]
    for index, (text, explanation) in enumerate(reference_texts):
        db.add(ReferenceStep(
            analysis_id=analysis.id,
            step_index=index,
            text=text,
            explanation=explanation,
            math_valid=True,
        ))
    db.add(Diagnosis(
        question_id=question.id,
        first_error_step=0,
        first_error_text="把两条直角边直接相加得到斜边。",
        error_type="formula_selection",
        root_misconception="没有识别出直角三角形应使用勾股定理，而不是把边长直接相加。",
        propagated_errors=["因此得到错误答案7 cm"],
        strategy_candidates=["勾股拼图", "比较三个正方形的面积"],
        confidence=1.0,
        error_location="学生路径第1步",
        missing_prerequisites=["识别斜边", "勾股定理"],
        recommended_strategy="通过勾股拼图观察两直角边平方和等于斜边平方。",
    ))
    return question


async def ensure_adaptive_practice_demo(db, student: User) -> Question:
    title = "二次函数参数讨论"
    question = await one(db, Question, Question.user_id == student.id, Question.title == title)
    if question is not None:
        mastery = await one(db, MasteryState, MasteryState.user_id == student.id,
                            MasteryState.subject == "数学",
                            MasteryState.knowledge_point == "参数讨论")
        if mastery is None:
            db.add(MasteryState(
                user_id=student.id, subject="数学", knowledge_point="参数讨论", mastery_score=0.51,
                confidence=0.62, evidence_count=2, update_reason="连续两次遗漏参数边界",
            ))
        return question
    question = Question(
        user_id=student.id, subject="数学", grade="高一", title=title,
        question_text="已知二次函数 f(x)=x²-2ax+a+2 在区间 [1,+∞) 上单调递增，求参数 a 的取值范围。",
        student_answer="a<1", status="diagnosed", confirmed=True,
        tags=["自适应练习"], knowledge_points=["二次函数", "参数讨论", "边界条件"],
        question_type="参数范围题",
    )
    db.add(question); await db.flush()
    analysis = ProblemAnalysis(
        question_id=question.id, subject="数学", problem_type="参数范围题",
        known_conditions=["二次函数", "区间 [1,+∞) 单调递增"], goal="求参数 a 的取值范围",
        knowledge_points=["二次函数", "参数讨论", "边界条件"],
        prerequisites=["二次函数对称轴", "单调区间"], final_answer="a≤1", verified=True,
    )
    db.add(analysis); await db.flush()
    db.add(Diagnosis(
        question_id=question.id, first_error_step=2,
        first_error_text="分类讨论时遗漏了 a=1 的边界情况。", error_type="boundary_omission",
        root_misconception="参数分类讨论策略不稳定，未单独验证临界值。",
        propagated_errors=["最终把 a≤1 写成 a<1"], confidence=1.0,
        error_location="参数分类步骤", missing_prerequisites=["边界情况判断"],
        recommended_strategy="先验证临界值，再写参数范围。",
    ))
    db.add(MasteryState(
        user_id=student.id, subject="数学", knowledge_point="参数讨论", mastery_score=0.51,
        confidence=0.62, evidence_count=2, update_reason="连续两次遗漏参数边界",
    ))
    return question


async def ensure_subject_practice_demo(
    db, student: User, *, subject: str, title: str, question_text: str,
    student_answer: str, knowledge_points: list[str], error_type: str,
    first_error: str, final_answer: str,
) -> Question:
    """Seed a personal mistake context; recommended questions still come from public datasets."""
    question = await one(db, Question, Question.user_id == student.id, Question.title == title)
    if question is not None:
        return question
    question = Question(
        user_id=student.id, subject=subject, grade="高一", title=title,
        question_text=question_text, student_answer=student_answer, status="diagnosed",
        confirmed=True, tags=["自适应练习"], knowledge_points=knowledge_points,
        question_type="综合题",
    )
    db.add(question); await db.flush()
    db.add(ProblemAnalysis(
        question_id=question.id, subject=subject, problem_type="综合题",
        known_conditions=[question_text], goal="得到正确结论", knowledge_points=knowledge_points,
        prerequisites=[], final_answer=final_answer, verified=True,
    ))
    db.add(Diagnosis(
        question_id=question.id, first_error_step=0, first_error_text=first_error,
        error_type=error_type, root_misconception=first_error, propagated_errors=[],
        confidence=1.0, error_location="关键判断", missing_prerequisites=knowledge_points[-1:],
        recommended_strategy="先确认研究对象和关键条件，再独立作答。",
    ))
    return question


async def seed() -> None:
    async with SessionLocal() as db:
        guardian = await ensure_user(db, "guardian@minddimension.local", "学习家长", "guardian")
        teacher = await ensure_user(db, "teacher@minddimension.local", "王老师", "teacher")
        await ensure_user(db, "admin@minddimension.local", "系统管理员", "admin")
        classroom = await one(db, TeacherClass, TeacherClass.teacher_id == teacher.id,
                              TeacherClass.name == "初二（1）班")
        if classroom is None:
            classroom = TeacherClass(teacher_id=teacher.id, name="初二（1）班")
            db.add(classroom); await db.flush()
        student_ids = []
        for email, name, subject, knowledge, misconception, score in STUDENTS:
            student = await ensure_user(db, email, name, "student", password="123456")
            student_ids.append(student.id)
            await ensure_student_data(db, student, subject, knowledge, misconception, score)
            if email == DEMO_STUDENT_EMAIL:
                await ensure_geometry_demo(db, student)
                await ensure_adaptive_practice_demo(db, student)
                await ensure_subject_practice_demo(
                    db, student, subject="物理", title="斜面受力分析",
                    question_text="物体静止在粗糙斜面上，请判断研究对象并分析物体受到的力。",
                    student_answer="只受到重力和支持力", knowledge_points=["力与受力分析", "受力对象"],
                    error_type="force_object_selection", first_error="没有先固定研究对象，漏掉了摩擦力。",
                    final_answer="受到重力、斜面支持力和静摩擦力。",
                )
                await ensure_subject_practice_demo(
                    db, student, subject="化学", title="离子方程式拆分判断",
                    question_text="写出稀盐酸与碳酸钙反应的离子方程式，并说明哪些物质不能拆分。",
                    student_answer="把碳酸钙拆成了离子", knowledge_points=["离子方程式", "可拆物质判断"],
                    error_type="ionic_split_error", first_error="把难溶的碳酸钙错误拆成了离子。",
                    final_answer="CaCO₃+2H⁺=Ca²⁺+CO₂↑+H₂O。",
                )
            if await one(db, GuardianStudentLink, GuardianStudentLink.guardian_id == guardian.id,
                         GuardianStudentLink.student_id == student.id) is None:
                db.add(GuardianStudentLink(guardian_id=guardian.id, student_id=student.id))
            if await one(db, TeacherClassStudent, TeacherClassStudent.class_id == classroom.id,
                         TeacherClassStudent.student_id == student.id) is None:
                db.add(TeacherClassStudent(class_id=classroom.id, student_id=student.id))
        await db.commit()
        print(f"demo_seed=ready students={len(student_ids)} class_id={classroom.id}")


if __name__ == "__main__":
    asyncio.run(seed())
