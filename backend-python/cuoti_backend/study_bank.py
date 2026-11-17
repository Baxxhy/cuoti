"""Grade-scoped public question bank, retaining seeded cross-subject ordering."""

import re
import time

from fastapi import APIRouter, Request

from .dataset_images import question_images
from .protocol import ApiError, envelope
from .question_data import rows, select_rows

router = APIRouter(prefix="/api/v1")
WHERE = " FROM dataset_questions q WHERE q.usable_for_practice=1 AND q.usable_for_auto_grade=1 AND q.has_answer=1 AND (?='' OR q.subject=?) AND (?='' OR q.grade_band=?) AND (?='' OR q.dataset_source_id=?) AND (?='' OR q.question_text LIKE ?)"


def student_grade(db, owner):
    found = rows(db, "SELECT grade FROM student_profiles WHERE user_id=?", [owner])
    grade = found[0]["grade"] if found else ""
    if grade not in ["初一", "初二", "初三", "高一", "高二", "高三"]:
        raise ApiError(422, "请先在学习设置中选择具体年级")
    return grade


def later_math(grade):
    college = "微积分|不定积分|定积分|微分方程|偏导数|拉普拉斯|傅里叶|泰勒级数|矩阵|行列式|特征值"
    if not grade.startswith("初"):
        return college
    senior = (
        college
        + "|复数|虚数|共轭|导数|求导|向量|数列|对数|指数函数|椭圆|双曲线|圆锥曲线|排列组合|二项式定理|数学归纳|充分条件|必要条件|奇函数|偶函数|等差|等比|正态分布|随机变量|(^|[^a-zA-Z])(log|ln)([^a-zA-Z]|$)"
    )
    if grade not in ["初一", "初二"]:
        return senior
    later = (
        senior
        + "|二次函数|一元二次|反比例函数|三角函数|正弦|余弦|正切|圆周角|圆心角|相似三角形|(^|[^a-zA-Z])(sin|cos|tan)([^a-zA-Z]|$)"
    )
    return (
        later + "|勾股|全等|二次根式|分式|一次函数|因式分解|完全平方|平方差"
        if grade == "初一"
        else later
    )


def scoped_where(grade):
    return WHERE + (
        " AND q.grade_band='高中'"
        if grade.startswith("高")
        else " AND q.grade IN (?,?) AND (q.subject<>'数学' OR CONCAT(q.question_text,' ',COALESCE(q.options,''),' ',COALESCE(q.knowledge_points,'')) NOT REGEXP ?)"
    )


def filters(grade, subject="", band="", source="", search=""):
    params = [subject, subject, band, band, source, source, search, "%" + search + "%"]
    if not grade.startswith("高"):
        params.extend(
            [
                grade,
                {"初一": "七年级", "初二": "八年级", "初三": "九年级"}.get(
                    grade, grade
                ),
                later_math(grade),
            ]
        )
    return params


def public(media, value):
    result = {
        key: value.get(key)
        for key in [
            "id",
            "subject",
            "grade",
            "grade_band",
            "title",
            "question_text",
            "question_type",
            "options",
            "difficulty",
            "knowledge_points",
            "source_name",
        ]
    }
    passage = (value.get("source_metadata") or {}).get("passage_id")
    if isinstance(passage, str) and passage:
        paragraphs = value["question_text"].split("\n\n")
        if len(paragraphs) > 1:
            result["preview_text"] = "阅读理解：" + paragraphs[-1]
    return {**result, **question_images(media, value)}


def query_integer(raw, default, maximum, message, minimum=0):
    raw = raw or str(default)
    if not re.fullmatch(r"[+-]?[0-9]+", raw) or not minimum <= int(raw) <= maximum:
        raise ApiError(422, message)
    return int(raw)


@router.get("/study-bank")
def browse(request: Request):
    values = request.query_params
    subject, band, source, search = (
        values.get(key, "") for key in ["subject", "grade_band", "source_id", "search"]
    )
    if any(
        len(value.encode()) > maximum
        for value, maximum in [
            (subject, 100),
            (band, 100),
            (source, 100),
            (search, 300),
        ]
    ):
        raise ApiError(422, "筛选条件过长")
    page = query_integer(values.get("page"), 1, 10000, "页码无效", 1)
    seed = query_integer(
        values.get("shuffle_seed"),
        int(time.time()) % 2147483647,
        2147483647,
        "随机顺序参数无效",
    )
    service = request.app.state.questions
    with service.database.session() as db:
        grade = student_grade(db, service.user(request, db).id)
        params, criteria = (
            filters(grade, subject, band, source, search),
            scoped_where(grade),
        )
        names = {
            row["id"]: row["name"]
            for row in rows(db, "SELECT id,name FROM dataset_sources")
        }
        paging = " LIMIT 20 OFFSET " + str((page - 1) * 20)
        key = "CRC32(CONCAT(q.id,':'," + str(seed) + "))"
        if not subject:
            sql = (
                "SELECT q.* FROM dataset_questions q JOIN (SELECT id,subject_rank,random_key FROM (SELECT q.id,ROW_NUMBER() OVER (PARTITION BY q.subject ORDER BY "
                + key
                + ",q.id) AS subject_rank,"
                + key
                + " AS random_key"
                + criteria
                + ") mixed ORDER BY subject_rank,random_key,id"
                + paging
                + ") selected ON selected.id=q.id ORDER BY selected.subject_rank,selected.random_key,selected.id"
            )
        else:
            sql = (
                "SELECT q.*"
                + criteria
                + (
                    " ORDER BY q.subject,q.id"
                    if grade.startswith("高")
                    else " ORDER BY q.grade,q.subject,q.id"
                )
                + paging
            )
        questions = []
        for value in select_rows(db, "dataset_questions", sql, params):
            value["source_name"] = names.get(value["dataset_source_id"], "题库")
            questions.append(public(service.media, value))
        facets, sources, total = {}, {}, 0
        for row in rows(
            db,
            "SELECT q.subject,q.grade_band,q.dataset_source_id,COUNT(*) AS total"
            + criteria
            + " GROUP BY q.subject,q.grade_band,q.dataset_source_id",
            filters(grade),
        ):
            row_subject, row_band, row_source, amount = (
                row["subject"],
                row["grade_band"],
                row["dataset_source_id"],
                int(row["total"]),
            )
            facet = facets.setdefault(
                (row_subject, row_band),
                {"subject": row_subject, "grade_band": row_band, "count": 0},
            )
            facet["count"] += amount
            sources[row_source] = sources.get(row_source, 0) + amount
            if (
                (not subject or subject == row_subject)
                and (not band or band == row_band)
                and (not source or source == row_source)
            ):
                total += amount
        if search:
            total = int(
                rows(db, "SELECT COUNT(*) AS total" + criteria, params)[0]["total"]
            )
        return envelope(
            request,
            {
                "page": page,
                "page_size": 20,
                "grade": grade,
                "scope_label": "高中" if grade.startswith("高") else grade,
                "shuffle_seed": seed,
                "questions": questions,
                "total": total,
                "facets": list(facets.values()),
                "sources": [
                    {"id": id, "name": names.get(id, "题库"), "count": amount}
                    for id, amount in sources.items()
                ],
            },
        )
