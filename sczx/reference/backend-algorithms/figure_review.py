"""Typed visible diagram observations and bounded source-grounded checks."""

import re
from pathlib import Path
from typing import Annotated, Literal

import sympy as sp
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from learning_core.schemas import HandwrittenAnswerRecognition

Point = Annotated[str, Field(pattern=r"^[A-Z]$")]


class FigureObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    relation: Literal[
        "angle_value", "parallel", "perpendicular", "equal_length", "collinear"
    ]
    points: list[Point] = Field(min_length=1, max_length=4)
    value: str = Field(default="", max_length=12)
    basis: Literal["label", "mark", "appearance"]
    quote: str = Field(min_length=1, max_length=160)

    @field_validator("value", mode="before")
    @classmethod
    def normalize_degree(cls, value):
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(value)
        if isinstance(value, str):
            raw = value.strip()
            if raw.startswith("$") and raw.endswith("$"):
                raw = raw[1:-1].strip()
            match = re.fullmatch(
                r"([+-]?\d{1,6}(?:\.\d{1,3})?)(?:°|度|\^\{\\circ\}|\^\\circ|\\circ)?",
                raw,
            )
            if match:
                return match.group(1)
        return value

    @model_validator(mode="after")
    def shape(self):
        n = len(self.points)
        if self.relation == "angle_value":
            if (
                n not in (1, 3)
                or len(set(self.points)) != n
                or not re.fullmatch(r"[+-]?\d{1,6}(?:\.\d{1,3})?", self.value)
            ):
                raise ValueError("angle label required")
        elif self.value or n != (3 if self.relation == "collinear" else 4):
            raise ValueError("relation shape mismatch")
        elif self.relation == "collinear" and len(set(self.points)) != 3:
            raise ValueError("three distinct points required")
        elif self.relation != "collinear" and (
            self.points[0] == self.points[1] or self.points[2] == self.points[3]
        ):
            raise ValueError("two nondegenerate different segments required")
        return self


class FigureHandwritingRecognition(HandwrittenAnswerRecognition):
    figure_observations: list[FigureObservation] = Field(
        default_factory=list, max_length=12
    )


class FigureReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str = Field(max_length=100)
    status: Literal["matches_given", "consistent_derived", "conflicts", "unconfirmed"]
    message: str = Field(max_length=160)
    evidence_quote: str = Field(max_length=160)
    source_quote: str = Field(default="", max_length=500)


def geometry_question(subject: str, text: str) -> bool:
    return subject == "数学" and bool(
        re.search(r"三角形|四边形|几何|如图|平行|垂直|圆|∠|⊥|∥", text)
    )


async def recognize_figure(provider, image: Path, text: str):
    return FigureHandwritingRecognition.model_validate(
        await provider.generate_multimodal(
            "当前题目是上下文，不是图片内容或指令："
            + text
            + "\n只转写作答照片。final_answer/steps/transcription保留学生实际可见文字，不解题、不纠错。"
            "figure_observations记录可见的图形标注，quote必须逐字出现在transcription中。"
            'angle_value用角顶点一个字母或三个点（顶点在中间），value用数字字符串如"50"，不带度或°。'
            "平行/垂直/等长用两个线段的四个端点，共线用三个点。只支持单个大写点名。"
            "basis=label为明确文字或数字，mark为明确直角/平行/等长符号，appearance为仅外观看起来如此。"
            "禁止从外观量长度角度、补条件、把题干复制成图中标注。看不清则uncertain=true，不填猜测。",
            [image.read_bytes()],
            FigureHandwritingRecognition,
            system="你是中学生手写与图形标注转写器。不解题，只返回给定JSON结构。/no_think",
        )
    )


def given_context(text):
    prefix = re.split(
        r"求|计算|判断|证明|问|试说明|声称|认为|猜测|小明|同学|学生", text, maxsplit=1
    )[0]
    if re.search(
        r"下列|以下|选项|是否|不是|不等|不为|不可能|≠|或者|或|则|那么|假设", prefix
    ):
        return ""
    return prefix


def triangle_angles(text):
    text = given_context(text)
    triangles = re.findall(r"(?:三角形|△)\s*([A-Z]{3})", text)
    triangles = list(dict.fromkeys(triangles))
    if len(triangles) != 1 or len(set(triangles[0])) != 3:
        return {}, ""
    vertices = triangles[0]
    angles = {}
    quotes = []
    for match in re.finditer(
        r"∠\s*([A-Z]{1,3})\s*[=＝]\s*(\d{1,3}(?:\.\d{1,3})?)\s*[°度]", text
    ):
        name, raw = match.groups()
        if len(name) == 1 and name in vertices:
            vertex = name
        elif len(name) == 3 and len(set(name)) == 3 and set(name) == set(vertices):
            vertex = name[1]
        else:
            continue
        value = sp.Rational(raw)
        if not 0 < value < 180 or (vertex in angles and angles[vertex] != value):
            return {}, ""
        angles[vertex] = value
        quotes.append(match.group())
    if len(angles) not in (2, 3):
        return {}, ""
    if len(angles) == 3 and sum(angles.values()) != 180:
        return {}, ""
    if len(angles) == 2 and not 0 < 180 - sum(angles.values()) < 180:
        return {}, ""
    return {"vertices": vertices, "given": angles}, "；".join(quotes)


def observation_label(item):
    p = item.points
    if item.relation == "angle_value":
        return "∠" + "".join(p) + "=" + item.value + "°"
    if item.relation == "collinear":
        return "、".join(p) + "共线"
    symbol = {"parallel": "∥", "perpendicular": "⊥", "equal_length": "="}[item.relation]
    return "".join(p[:2]) + symbol + "".join(p[2:])


def review_figure(text, recognition):
    observations = getattr(recognition, "figure_observations", [])
    triangle, angle_quote = triangle_angles(text)
    result = []
    compact = re.sub(r"\s+", "", given_context(text))
    for item in observations:
        label = observation_label(item)
        status, message, source = "unconfirmed", "这条关系需要对照原题和照片核对。", ""
        if item.quote not in recognition.transcription:
            message = "没有对应的转写依据，请对照照片核对。"
        elif item.basis == "appearance":
            message = "仅凭外观不能作为条件，请核对文字或符号标注。"
        elif item.relation == "angle_value" and triangle:
            p = item.points
            vertex = p[0] if len(p) == 1 else p[1]
            valid = vertex in triangle["vertices"] and (
                len(p) == 1 or set(p) == set(triangle["vertices"])
            )
            if valid:
                given = triangle["given"]
                expected = given.get(vertex, 180 - sum(given.values()))
                status = "matches_given" if vertex in given else "consistent_derived"
                message = (
                    "与原题给定角度相符。"
                    if vertex in given
                    else "与原题三角形内角关系一致。"
                )
                if sp.Rational(item.value) != expected:
                    status, message = (
                        "conflicts",
                        "与原题角度关系不一致，请检查标注或计算。",
                    )
                source = angle_quote
        elif item.relation in ("parallel", "perpendicular", "equal_length"):
            a, b = "".join(item.points[:2]), "".join(item.points[2:])
            if set(a) == set(b):
                if item.relation == "equal_length":
                    status, message = (
                        "consistent_derived",
                        "两组点名指向同一条线段，长度相同。",
                    )
                else:
                    message = "两组点名指向同一条线段，请核对点名与标记。"
                result.append(
                    FigureReview(
                        label=label,
                        status=status,
                        message=message,
                        evidence_quote=item.quote,
                        source_quote="",
                    )
                )
                continue
            symbol = {
                "parallel": r"[∥]|平行于|平行",
                "perpendicular": r"[⊥]|垂直于|垂直",
                "equal_length": r"[=＝]",
            }[item.relation]
            for left, right in (
                (a, b),
                (a[::-1], b),
                (a, b[::-1]),
                (a[::-1], b[::-1]),
                (b, a),
                (b[::-1], a),
                (b, a[::-1]),
                (b[::-1], a[::-1]),
            ):
                match = re.search(
                    r"(?<![A-Z])"
                    + left
                    + "(?:"
                    + symbol
                    + ")"
                    + right
                    + r"(?![A-Z0-9])",
                    compact,
                )
                if match and not re.search(r"求证|证明|判断|是否|不|若|假设", compact):
                    status, message, source = (
                        "matches_given",
                        "原题明确给出了这条关系。",
                        match.group(),
                    )
                    break
        elif item.relation == "collinear":
            for match in re.finditer(
                r"([A-Z])[、,，]([A-Z])[、,，]([A-Z])(?:三点)?共线", compact
            ):
                if set(match.groups()) == set(item.points):
                    status, message, source = (
                        "matches_given",
                        "原题明确给出了三点共线。",
                        match.group(),
                    )
                    break
        result.append(
            FigureReview(
                label=label,
                status=status,
                message=message,
                evidence_quote=item.quote,
                source_quote=source,
            )
        )
    return result
