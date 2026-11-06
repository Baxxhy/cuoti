"""Source-bound, executable-code-free task diagrams and finite controls."""

from __future__ import annotations

import math
import re
from typing import Annotated, Literal

import sympy as sp
from pydantic import BaseModel, ConfigDict, Field

from learning_core.services.math_tools import normalize_expression, parse_math_expression


class StrictVisualModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


Number = Annotated[float, Field(ge=-100000000, le=100000000, strict=True)]


class VisualVariable(StrictVisualModel):
    name: Literal["delta", "k", "b", "a", "h"]
    label: str = Field(max_length=40)
    min: Number
    max: Number
    step: Number
    value: Number


class TaskVisualSpec(StrictVisualModel):
    schema_version: Literal["1.0"] = "1.0"
    type: Literal["equation_balance", "linear_function", "quadratic_function"]
    title: str = Field(max_length=80)
    teaching_goal: str = Field(max_length=160)
    parameters: dict[str, Number | bool] = Field(max_length=8)
    interactive_variables: list[VisualVariable] = Field(max_length=3)
    highlights: list = Field(default_factory=list, max_length=0)
    annotations: list = Field(default_factory=list, max_length=0)
    student_task: str = Field(max_length=160)
    expected_observation: str = Field(max_length=160)


class TaskVisualization(StrictVisualModel):
    rule_version: Literal["task-visual-v1"] = "task-visual-v1"
    source_question_id: str = Field(min_length=1, max_length=36)
    source_phase: Literal["repair", "independent", "contrast"]
    source_equation_tex: str = Field(max_length=1000)
    current_equation_tex: str = Field(max_length=1000)
    scope: Literal["equation_relation", "function_expression"]
    spec: TaskVisualSpec
    values: dict[str, Number] = Field(max_length=3)
    observation: str = Field(default="", max_length=1200)


def variable(name, label, low, high, step, value):
    return VisualVariable(
        name=name,
        label=label,
        min=float(low),
        max=float(high),
        step=float(step),
        value=float(value),
    )


def finite_controls(variables: list[VisualVariable], supplied: dict | None):
    defaults = {v.name: v.value for v in variables}
    if supplied is None:
        return defaults
    if set(supplied) != set(defaults):
        raise ValueError("visualization controls do not match source")
    result = {}
    for v in variables:
        value = supplied[v.name]
        if type(value) not in (int, float) or not v.min <= value <= v.max:
            raise ValueError("visualization control out of range")
        if abs((value - v.min) / v.step - round((value - v.min) / v.step)) > 1e-7:
            raise ValueError("visualization control off grid")
        result[v.name] = float(value)
    return result


def source_function(text: str):
    raw = normalize_expression(text).strip("。 ")
    raw = re.sub(r"^(?:函数|一次函数|二次函数)[：:\s]*", "", raw)
    if len(raw) > 300 or not re.fullmatch(r"y\s*=\s*[0-9x+*/().\s-]+", raw):
        return None
    try:
        rhs = raw.split("=", 1)[1]
        # Keep finite decimals exact before symbolic polynomial validation.
        rhs = re.sub(
            r"(?<![\w.])(?:\d+\.\d*|\.\d+)",
            lambda m: "(" + str(sp.Rational(m[0])) + ")",
            rhs,
        )
        expression = parse_math_expression(rhs)
        x = sp.Symbol("x")
        if expression.free_symbols != {x} or expression.has(sp.Float):
            return None
        # A variable denominator is a domain restriction even when simplifiable.
        if re.search(r"/\s*(?:x|\([^)]*x)|\*\*\s*\(?\s*-", raw):
            return None
        polynomial = sp.Poly(expression, x)
        if polynomial.degree() not in (1, 2):
            return None
        return polynomial, x
    except (ValueError, TypeError, SyntaxError, sp.PolynomialError):
        return None


def build_task_visualization(
    *,
    question: str,
    subject: str,
    question_id: str,
    phase: str,
    linear=None,
    values=None,
):
    if subject != "数学" or phase == "done":
        return None
    if linear is not None:
        _, x, a, b, c, _ = linear
        if any(not v.is_finite or abs(v) > 10000 for v in (a, b, c)):
            return None
        limit = min(20, max(5, int(sp.ceiling(abs(b))) + 2))
        variables = [variable("delta", "两边同时减去", -limit, limit, 1, 0)]
        controls = finite_controls(variables, values)
        delta = sp.Rational(str(controls["delta"]))
        left, right = a * x + b - delta, c - delta
        if sp.simplify((left - right) - (a * x + b - c)) != 0:
            raise ValueError("equivalence verification failed")
        spec = TaskVisualSpec(
            type="equation_balance",
            title="等式两边同操作",
            teaching_goal="观察同一运算如何保持等式关系",
            parameters={"left": float(c), "right": float(c), "task_bound": True},
            interactive_variables=variables,
            student_task="调一下数，看看等号两边怎样变化。",
            expected_observation="两边做相同运算，等价关系保持不变。",
        )
        return TaskVisualization(
            source_question_id=question_id,
            source_phase=phase,
            source_equation_tex=sp.latex(a * x + b) + "=" + sp.latex(c),
            current_equation_tex=sp.latex(left) + "=" + sp.latex(right),
            scope="equation_relation",
            spec=spec,
            values=controls,
        )
    function = source_function(question)
    if function is None:
        return None
    polynomial, x = function
    if polynomial.degree() == 1:
        k, b = polynomial.nth(1), polynomial.nth(0)
        if any(abs(v) > 10000 for v in (k, b)):
            return None
        k_step, b_step = max(0.5, abs(float(k)) / 4), max(0.25, abs(float(k)) / 4)
        variables = [
            variable(
                "k", "斜率 k", float(k) - 5 * k_step, float(k) + 5 * k_step, k_step, k
            ),
            variable(
                "b", "截距 b", float(b) - 5 * b_step, float(b) + 5 * b_step, b_step, b
            ),
        ]
        kind, parameters = "linear_function", {"k": float(k), "b": float(b)}
        center_x, center_y = 0.0, float(b)
        extent = max(6.0, abs(float(k)) * 4 + 5 * b_step)
    else:
        a, h = polynomial.nth(2), -polynomial.nth(1) / (2 * polynomial.nth(2))
        k = polynomial.eval(h)
        if any(abs(v) > 10000 for v in (a, h, k)):
            return None
        if sp.expand(a * (x - h) ** 2 + k - polynomial.as_expr()) != 0:
            return None
        a_step, k_step = max(0.5, abs(float(a)) / 4), max(0.25, abs(float(a)) / 4)
        variables = [
            variable(
                "a",
                "开口系数 a",
                float(a) - 5 * a_step,
                float(a) + 5 * a_step,
                a_step,
                a,
            ),
            variable("h", "水平平移 h", float(h) - 3, float(h) + 3, 0.5, h),
            variable(
                "k",
                "竖直平移 k",
                float(k) - 5 * k_step,
                float(k) + 5 * k_step,
                k_step,
                k,
            ),
        ]
        kind, parameters = (
            "quadratic_function",
            {"a": float(a), "h": float(h), "k": float(k)},
        )
        center_x, center_y = float(h), float(k)
        extent = max(6.0, abs(float(a)) * 9 + 5 * k_step)
    # Keep the viewport tied to the original expression while controls move the curve.
    tick_base = 10 ** math.floor(math.log10(extent / 3))
    tick = next(m * tick_base for m in (1, 2, 5, 10) if m * tick_base >= extent / 3)
    parameters.update(
        center_x=center_x, center_y=center_y, x_span=6.0, y_span=float(3 * tick)
    )
    controls = finite_controls(variables, values)
    new_expression = (
        sp.Rational(str(controls["k"])) * x + sp.Rational(str(controls["b"]))
        if kind == "linear_function"
        else sp.Rational(str(controls["a"]))
        * (x - sp.Rational(str(controls["h"]))) ** 2
        + sp.Rational(str(controls["k"]))
    )
    if controls == {v.name: v.value for v in variables}:
        new_expression = polynomial.as_expr()
    spec = TaskVisualSpec(
        type=kind,
        title="函数参数与图像",
        teaching_goal="从原式出发观察参数改变",
        parameters=parameters,
        interactive_variables=variables,
        student_task="改一个参数，观察图像的变化。",
        expected_observation="参数变化后的图像是对照示例，不是原题的新答案；a为0时不再是二次函数。"
        if kind == "quadratic_function"
        else "参数变化后的图像是对照示例，不是原题的新答案；k为0时不再是一次函数。",
    )
    return TaskVisualization(
        source_question_id=question_id,
        source_phase=phase,
        source_equation_tex="y=" + sp.latex(polynomial.as_expr()),
        current_equation_tex="y=" + sp.latex(new_expression),
        scope="function_expression",
        spec=spec,
        values=controls,
    )
