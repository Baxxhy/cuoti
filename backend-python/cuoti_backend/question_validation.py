import math
import re

from .protocol import ApiError


def text_value(value, maximum, *, minimum=0, trim=False, nullable=False):
    if value is None and nullable:
        return None
    if not isinstance(value, str):
        raise ApiError(422, "输入文字格式或长度不正确")
    value = value.strip() if trim else value
    if not minimum <= len(value) <= maximum:
        raise ApiError(422, "输入文字格式或长度不正确")
    return value


def array(body, key, maximum):
    value = body.get(key, [])
    if not isinstance(value, list) or len(value) > maximum:
        raise ApiError(422, f"{key} 格式或数量不正确")
    return value


def number(value):
    try:
        result = float(value)
        if math.isfinite(result):
            return result
    except (ValueError, TypeError, OverflowError):
        pass
    raise ApiError(422, "数字格式不正确")


def boolean(value):
    if isinstance(value, bool):
        return value
    if type(value) in (int, float) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        if value.lower() in ["1", "true", "t", "yes", "y", "on"]:
            return True
        if value.lower() in ["0", "false", "f", "no", "n", "off", ""]:
            return False
    raise ApiError(422, "收藏状态格式不正确")


def step_object(value, teacher=False):
    return (
        value if isinstance(value, dict) else {"comment" if teacher else "text": value}
    )


def step_text(value):
    item = step_object(value)
    return item.get("text", item.get("raw_text", ""))


def validate_steps(values, teacher=False):
    for value in values:
        if isinstance(value, str):
            text_value(value, 12000)
            continue
        if not isinstance(value, dict):
            raise ApiError(422, "步骤格式不正确")
        for key in (
            ["comment"]
            if teacher
            else ["text", "raw_text", "normalized_text", "formula"]
        ):
            if key in value:
                text_value(value[key], 12000)
        for key in ["mark_type"] if teacher else ["source"]:
            if key in value:
                text_value(value[key], 50)
        if "confidence" in value and not 0 <= number(value["confidence"]) <= 1:
            raise ApiError(422, "置信度超出范围")
        if "bbox" in value:
            if not isinstance(value["bbox"], list) or len(value["bbox"]) > 4:
                raise ApiError(422, "坐标数量不正确")
            for coordinate in value["bbox"]:
                number(coordinate)


def edits(body):
    result = {}
    specs = {
        "question_text": (12000, 1, True, False),
        "student_answer": (12000, 0, False, True),
        "grade": (30, 0, False, True),
        "subject": (30, 1, True, False),
        "question_type": (50, 1, False, False),
        "title": (255, 0, False, False),
    }
    for key, value in body.items():
        if key in specs:
            maximum, minimum, trim, nullable = specs[key]
            result[key] = text_value(
                value, maximum, minimum=minimum, trim=trim, nullable=nullable
            )
        elif key == "favorite":
            result[key] = boolean(value)
        elif key in [
            "tags",
            "formulas",
            "knowledge_points",
            "options",
            "student_steps",
            "teacher_marks",
        ]:
            limit = (
                26
                if key == "options"
                else 50
                if key in ["tags", "knowledge_points"]
                else 100
            )
            values = array(body, key, limit)
            if key in ["student_steps", "teacher_marks"]:
                validate_steps(values, key == "teacher_marks")
                continue
            cleaned = []
            for item in values:
                if key == "options":
                    if not isinstance(item, dict):
                        raise ApiError(422, "选项格式不正确")
                    label = text_value(item.get("label"), 8, minimum=1, trim=True)
                    if any(entry["label"] == label for entry in cleaned):
                        raise ApiError(422, "选项标记不能重复")
                    cleaned.append(
                        {"label": label, "text": text_value(item.get("text"), 12000)}
                    )
                else:
                    cleaned.append(
                        text_value(
                            item,
                            12000 if key == "formulas" else 30,
                            minimum=0 if key == "formulas" else 1,
                            trim=key != "formulas",
                        )
                    )
            result[key] = cleaned
    return result


def crop_box(body):
    try:
        values = body["box"]
        if (
            not isinstance(values, list)
            or len(values) != 4
            or any(isinstance(v, bool) for v in values)
        ):
            raise ValueError
        x, y, w, h = [number(value) for value in values]
        if (
            0 <= x < 1
            and 0 <= y < 1
            and 0 < w <= 1
            and 0 < h <= 1
            and x + w <= 1.000001
            and y + h <= 1.000001
        ):
            return [x, y, w, h]
    except (KeyError, TypeError, ValueError, ApiError):
        pass
    raise ApiError(422, "裁剪范围无效，请重新框选题目")


def inferred_choice(steps, options):
    texts = [
        step_text(value).strip().upper() for value in steps if step_text(value).strip()
    ]
    if len(texts) != 1:
        return None
    known = {
        str(item.get("label", item.get("key", ""))).upper()
        for item in options
        if isinstance(item, dict)
    }
    compact = re.sub(r"\s+", "", texts[0])
    if not re.fullmatch(r"[A-Z](?:[、,，][A-Z])*", compact):
        return None
    labels = re.split("[、,，]", compact)
    if known and any(label not in known for label in labels):
        return None
    return "、".join(dict.fromkeys(labels))


def short_title(value, limit):
    if len(value) > limit:
        prefix = value[:limit]
        positions = [prefix.index(c) for c in ["$", "\\"] if c in prefix]
        if positions:
            clean = prefix[: min(positions)]
            return clean + "…" if clean.strip() else "题目详情"
    return value[:limit] or "待确认错题"
