from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.schemas import VisualizationPayload


def _spec(
    kind: str,
    title: str,
    goal: str,
    task: str,
    observation: str,
    parameters: dict[str, Any],
    variables: list[dict[str, Any]],
) -> dict[str, Any]:
    return VisualizationPayload(
        type=kind,
        title=title,
        teaching_goal=goal,
        parameters=parameters,
        interactive_variables=variables,
        student_task=task,
        expected_observation=observation,
    ).model_dump()


VISUALIZATION_SPECS: dict[str, dict[str, Any]] = {
    "triangle": _spec(
        "triangle",
        "三角形边角关系",
        "观察顶点移动对边角的影响",
        "拖动顶点高度并判断三边关系",
        "任意两边之和大于第三边",
        {"base": 8, "height": 5},
        [{"name": "height", "label": "顶点高度", "min": 2, "max": 9, "step": 1, "value": 5}],
    ),
    "right_triangle": _spec(
        "right_triangle",
        "勾股拼图",
        "验证直角三角形三边平方关系",
        "改变直角边并比较三个正方形面积",
        "两直角边平方和等于斜边平方",
        {"a": 3, "b": 4},
        [
            {"name": "a", "label": "直角边 a", "min": 2, "max": 7, "step": 1, "value": 3},
            {"name": "b", "label": "直角边 b", "min": 2, "max": 7, "step": 1, "value": 4},
        ],
    ),
    "circle": _spec(
        "circle",
        "圆周角实验",
        "理解同弧所对圆周角",
        "移动圆周点并比较角度",
        "同弧所对圆周角相等，圆心角是其两倍",
        {"radius": 76},
        [{"name": "angle", "label": "圆周点位置", "min": 25, "max": 155, "step": 5, "value": 80}],
    ),
    "linear_function": _spec(
        "linear_function",
        "一次函数探究",
        "理解斜率和截距",
        "调整 k、b 观察直线",
        "k 控制倾斜方向和陡峭程度，b 控制纵轴截距",
        {"k": 1, "b": 0},
        [
            {"name": "k", "label": "斜率 k", "min": -3, "max": 3, "step": 0.5, "value": 1},
            {"name": "b", "label": "截距 b", "min": -4, "max": 4, "step": 1, "value": 0},
        ],
    ),
    "quadratic_function": _spec(
        "quadratic_function",
        "抛物线变换",
        "理解顶点式参数",
        "调整 a、h、k 观察开口和顶点",
        "a 控制开口，(h,k) 是顶点",
        {"a": 1, "h": 0, "k": 0},
        [
            {"name": "a", "label": "开口 a", "min": -2, "max": 2, "step": 0.5, "value": 1},
            {"name": "h", "label": "水平平移 h", "min": -3, "max": 3, "step": 1, "value": 0},
            {"name": "k", "label": "竖直平移 k", "min": -3, "max": 3, "step": 1, "value": 0},
        ],
    ),
    "coordinate_geometry": _spec(
        "coordinate_geometry",
        "坐标几何",
        "用坐标变化理解距离和中点",
        "移动点 B 并读取中点",
        "中点坐标是对应坐标的平均数",
        {"ax": -3, "ay": -2},
        [
            {"name": "bx", "label": "B 点横坐标", "min": -4, "max": 4, "step": 1, "value": 3},
            {"name": "by", "label": "B 点纵坐标", "min": -4, "max": 4, "step": 1, "value": 2},
        ],
    ),
    "equation_balance": _spec(
        "equation_balance",
        "等式天平",
        "理解等式两边同操作",
        "调节两边同时减去的数",
        "两边执行相同操作，等式仍成立",
        {"left": 11, "right": 11},
        [{"name": "delta", "label": "两边同时减去", "min": -5, "max": 5, "step": 1, "value": 3}],
    ),
    "uniform_motion": _spec(
        "uniform_motion",
        "匀速运动",
        "建立路程—时间模型",
        "调节时间观察位置",
        "相同时间内通过的路程相等，s=vt",
        {"speed": 2},
        [{"name": "time", "label": "时间 t", "min": 0, "max": 10, "step": 1, "value": 4}],
    ),
    "uniform_acceleration": _spec(
        "uniform_acceleration",
        "匀加速 v-t 图",
        "理解速度随时间线性变化",
        "调节加速度观察斜率和面积",
        "斜率是加速度，图像下方面积是位移",
        {"v0": 1},
        [
            {"name": "acceleration", "label": "加速度 a", "min": -2, "max": 3, "step": 0.5, "value": 1},
            {"name": "time", "label": "时间 t", "min": 1, "max": 8, "step": 1, "value": 5},
        ],
    ),
    "projectile_motion": _spec(
        "projectile_motion",
        "抛体运动分解",
        "观察水平与竖直分运动",
        "调整初速度观察轨迹和落点",
        "水平匀速、竖直加速，两者共享时间",
        {"gravity": 9.8},
        [
            {"name": "speed", "label": "初速度", "min": 4, "max": 14, "step": 1, "value": 9},
            {"name": "launch_angle", "label": "发射角", "min": 20, "max": 70, "step": 5, "value": 45},
        ],
    ),
    "force_diagram": _spec(
        "force_diagram",
        "受力分析",
        "区分支持力、重力和外力",
        "改变外力并判断合力方向",
        "箭头方向表示力方向，长度表示大小",
        {"gravity": 5, "normal": 5},
        [{"name": "applied", "label": "水平外力", "min": -6, "max": 6, "step": 1, "value": 3}],
    ),
    "work_energy": _spec(
        "work_energy",
        "功与能量转换",
        "理解动能和势能转换",
        "调节高度观察能量柱",
        "忽略阻力时总机械能保持不变",
        {"total": 10},
        [{"name": "height", "label": "相对高度", "min": 0, "max": 10, "step": 1, "value": 6}],
    ),
    "pressure": _spec(
        "pressure",
        "压力与压强",
        "理解受力面积影响压强",
        "改变接触面积比较压强",
        "压力相同时，受力面积越小压强越大",
        {"force": 8},
        [{"name": "area", "label": "接触面积", "min": 1, "max": 8, "step": 1, "value": 4}],
    ),
    "buoyancy": _spec(
        "buoyancy",
        "浮力与排液",
        "理解排开液体体积",
        "调节浸入比例观察浮力",
        "浸入体积越大，浮力越大",
        {"density": 1},
        [{"name": "submerged", "label": "浸入比例", "min": 0, "max": 100, "step": 10, "value": 60}],
    ),
    "history_timeline": _spec(
        "history_timeline",
        "历史时间轴",
        "建立事件先后与因果",
        "移动观察窗口定位事件",
        "时间先后是因果判断的必要条件但不是充分条件",
        {"events": ["新航路开辟", "工业革命", "法国大革命", "第二次工业革命"]},
        [{"name": "focus", "label": "时间窗口", "min": 0, "max": 3, "step": 1, "value": 1}],
    ),
    "timeline_map": _spec(
        "timeline_map",
        "时空关联图",
        "同时理解地点、传播和时间",
        "切换阶段观察事件传播",
        "历史变化沿交通与社会联系扩散",
        {"places": ["英国", "法国", "德国", "中国"]},
        [{"name": "stage", "label": "传播阶段", "min": 0, "max": 3, "step": 1, "value": 2}],
    ),
}


def visualization_spec(kind: str) -> dict[str, Any]:
    if kind not in VISUALIZATION_SPECS:
        kind = "equation_balance"
    return deepcopy(VISUALIZATION_SPECS[kind])


def visualization_catalog() -> list[dict[str, Any]]:
    return [deepcopy(item) for item in VISUALIZATION_SPECS.values()]


def recommended_visualization(subject: str, question_type: str, knowledge_points: list[Any]) -> str | None:
    text = " ".join([subject, question_type, *(str(item) for item in knowledge_points)]).lower()
    rules = (
        (("勾股", "直角三角形"), "right_triangle"),
        (("圆周角", "圆心角", "圆"), "circle"),
        (("坐标", "中点", "两点距离"), "coordinate_geometry"),
        (("三角形", "全等", "相似"), "triangle"),
        (("二次函数", "抛物线"), "quadratic_function"),
        (("一次函数", "直线函数"), "linear_function"),
        (("方程", "等式", "移项"), "equation_balance"),
        (("匀加速", "速度时间", "v-t"), "uniform_acceleration"),
        (("抛体", "平抛", "斜抛"), "projectile_motion"),
        (("匀速", "路程", "s=vt"), "uniform_motion"),
        (("受力", "合力", "支持力"), "force_diagram"),
        (("机械能", "动能", "势能", "功与能"), "work_energy"),
        (("压强", "压力"), "pressure"),
        (("浮力", "排液"), "buoyancy"),
        (("时间轴", "年代", "先后顺序"), "history_timeline"),
        (("时空", "传播", "地图"), "timeline_map"),
    )
    for keywords, kind in rules:
        if any(keyword in text for keyword in keywords):
            return kind
    return None
