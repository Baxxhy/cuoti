from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

CORE_SUBJECTS = ("语文", "数学", "英语", "物理", "化学", "生物", "历史", "地理", "道德与法治", "思想政治")
MIDDLE_SCHOOL_GRADES = ("初一", "初二", "初三", "高一", "高二", "高三")


@dataclass(frozen=True)
class SubjectPedagogy:
    reasoning_focus: str
    prerequisite_prompt: str
    guided_prompt: str
    partial_prompt: str
    alternate_prompt: str
    teach_back_prompt: str
    teach_back_keywords: tuple[tuple[str, ...], ...]
    error_taxonomy: dict[str, str]


COMMON_ERRORS = {
    "missing_step": "缺少步骤",
    "condition_omission": "漏用条件",
    "concept_error": "概念理解错误",
    "reasoning_gap": "推理不完整",
}


SUBJECT_PEDAGOGY: dict[str, SubjectPedagogy] = {
    "数学": SubjectPedagogy(
        "条件、数学关系与等价推导",
        "先找出已知量、未知量和它们之间的关系。",
        "只看出错的这一步：它使用了哪条定义、公式或运算规则？",
        "你已经找对了一部分关系。请保留它，再检查下一步运算是否仍与原式等价。",
        "换一种方法：代入检验、画图或用具体数字验证这一步。",
        "请说明用了哪条数学规则、为什么能用，以及怎样得到结论。",
        (("因为", "根据", "由"), ("所以", "得到", "可知", "因此")),
        {
            **COMMON_ERRORS,
            "sign_error": "符号错误",
            "calculation_error": "计算错误",
            "formula_error": "公式选择错误",
            "invalid_transformation": "变形不成立",
        },
    ),
    "物理": SubjectPedagogy(
        "研究对象、物理过程、公式条件与单位",
        "先确定研究对象和所处的物理过程，再列出已知量及单位。",
        "这一步使用了哪个物理规律？题目条件满足这个规律吗？",
        "物理过程判断基本正确。请保留它，再检查公式、方向或单位。",
        "换成受力图、过程图或极端情况，检查你的判断是否合理。",
        "请按“物理过程—规律—代入—单位—结论”讲一遍。",
        (("规律", "公式", "定律", "原理"), ("单位", "方向", "条件", "过程")),
        {
            **COMMON_ERRORS,
            "model_error": "物理模型判断错误",
            "formula_error": "公式选择错误",
            "unit_error": "单位错误",
            "direction_error": "方向判断错误",
            "calculation_error": "计算错误",
        },
    ),
    "化学": SubjectPedagogy(
        "物质、反应条件、守恒与实验现象",
        "先辨认物质和反应条件，再回忆相关性质或守恒关系。",
        "这一步依据的是物质性质、反应规律还是实验现象？条件是否完整？",
        "你判断对了一部分。请继续检查化学式、配平、条件或单位。",
        "换成微粒示意或守恒表，检查反应前后的元素和数量。",
        "请按“物质与条件—依据—现象或计算—结论”讲一遍。",
        (("反应", "性质", "守恒", "方程式", "实验"), ("条件", "现象", "所以", "结论")),
        {
            **COMMON_ERRORS,
            "substance_error": "物质判断错误",
            "equation_error": "化学方程式错误",
            "balance_error": "配平错误",
            "condition_error": "反应条件遗漏",
            "phenomenon_error": "实验现象混淆",
            "unit_error": "单位错误",
        },
    ),
    "语文": SubjectPedagogy(
        "文本证据、语境、表达作用与答题结构",
        "先回到原文，圈出题目对象和与它直接相关的句子。",
        "你的判断能从原文哪句话得到支持？结合语境说明。",
        "你已经找到了相关内容。请再说明这处文字怎样支持你的结论。",
        "换一个角度：从人物、情节、语言或结构作用重新找证据。",
        "请按“观点—原文证据—分析—结论”讲一遍。",
        (("原文", "文中", "句", "词", "描写", "证据"), ("说明", "表现", "表达", "体现", "作用")),
        {
            **COMMON_ERRORS,
            "evidence_missing": "缺少文本证据",
            "context_error": "脱离语境",
            "theme_error": "主旨理解偏差",
            "expression_error": "表达作用分析不完整",
            "language_error": "语言运用错误",
        },
    ),
    "英语": SubjectPedagogy(
        "语境、句子结构、语法形式与文本证据",
        "先判断题目考查词义、语法、阅读还是写作，再找上下文线索。",
        "请指出主干或上下文线索，再说明为什么选择这个形式或答案。",
        "你找到了一条有效线索。请继续核对时态、搭配、指代或逻辑关系。",
        "换成句子成分标注或把选项代回原句，比较语义和语法。",
        "请按“语境线索—语法或词义规则—答案”解释一遍。",
        (("语境", "句子", "原文", "时态", "语法", "搭配"), ("所以", "因此", "表示", "符合")),
        {
            **COMMON_ERRORS,
            "grammar_error": "语法错误",
            "vocabulary_error": "词义或搭配错误",
            "context_error": "语境理解错误",
            "reading_evidence_missing": "缺少阅读证据",
            "writing_error": "写作表达错误",
        },
    ),
    "生物": SubjectPedagogy(
        "结构、功能、过程、变量与实验依据",
        "先判断涉及哪个生命结构或过程，并找出实验变量或条件。",
        "这一步依据的是结构与功能关系，还是某个生命过程？",
        "对象或过程判断正确。请继续检查条件、变量和因果关系。",
        "换成结构图、流程图或对照实验表，重新检查结论。",
        "请按“对象或结构—过程或功能—证据—结论”讲一遍。",
        (("结构", "过程", "功能", "实验", "变量"), ("导致", "所以", "说明", "结论")),
        {
            **COMMON_ERRORS,
            "structure_function_error": "结构与功能混淆",
            "process_error": "生命过程理解错误",
            "variable_error": "实验变量判断错误",
            "control_error": "对照实验设置错误",
            "evidence_error": "实验依据不足",
        },
    ),
    "历史": SubjectPedagogy(
        "时空背景、史料证据、因果层次与影响",
        "先确定事件的时间、地点和背景，再区分题目问的是原因、经过还是影响。",
        "请从材料或史实中找一条证据，并说明它与结论的因果关系。",
        "史实基本找对了。请继续区分背景、直接原因、根本原因和影响。",
        "换成时间线或因果链，把事件前后的关系排出来。",
        "请按“背景或材料证据—因果关系—结论”讲一遍。",
        (("材料", "史实", "背景", "时间", "事件"), ("原因", "导致", "影响", "所以", "说明")),
        {
            **COMMON_ERRORS,
            "fact_error": "史实错误",
            "chronology_error": "时间顺序错误",
            "causality_confusion": "历史因果混淆",
            "evidence_missing": "缺少史料依据",
            "impact_error": "影响分析不完整",
        },
    ),
    "地理": SubjectPedagogy(
        "空间位置、地图信息、自然与人文要素联系",
        "先定位区域，读取图例、方向、比例尺或统计图中的关键信息。",
        "这个结论来自地图中的哪项信息？相关自然或人文因素是什么？",
        "区域或要素判断正确。请继续说明各因素如何共同产生结果。",
        "换成示意图、剖面图或因素关系图，从空间联系重新判断。",
        "请按“位置或图表信息—影响因素—过程—结论”讲一遍。",
        (("位置", "地图", "图中", "区域", "气候", "地形"), ("影响", "导致", "因此", "分布")),
        {
            **COMMON_ERRORS,
            "location_error": "空间位置判断错误",
            "map_reading_error": "地图信息读取错误",
            "factor_error": "影响因素遗漏",
            "spatial_relation_error": "空间关系混淆",
            "chart_error": "图表分析错误",
        },
    ),
    "道德与法治": SubjectPedagogy(
        "材料情境、核心概念、行为评价与规范依据",
        "先概括材料中的行为或矛盾，再找对应的教材观点和规范。",
        "材料中的哪个关键词对应这条观点？请把观点与行为联系起来。",
        "观点选择基本正确。请继续结合材料说明，避免只背结论。",
        "换成“行为—影响—规则—正确做法”四格分析。",
        "请按“材料事实—教材观点或规则—分析—正确做法”讲一遍。",
        (("材料", "行为", "观点", "规则", "法律", "权利", "义务"), ("说明", "体现", "因为", "应该")),
        {
            **COMMON_ERRORS,
            "material_mismatch": "材料与观点不匹配",
            "concept_confusion": "概念混淆",
            "rule_error": "规则或法律依据错误",
            "action_missing": "缺少正确做法",
        },
    ),
    "思想政治": SubjectPedagogy(
        "材料逻辑、学科概念、原理与现实联系",
        "先概括材料主旨，再确定所属模块和可以调用的学科原理。",
        "材料中的哪一信息对应这个原理？二者之间是什么逻辑关系？",
        "原理选择基本正确。请继续结合材料展开，而不是只写原理名称。",
        "换成“材料关键词—原理—分析对象—结论”的对应表。",
        "请按“材料信息—学科原理—具体分析—结论”讲一遍。",
        (
            ("材料", "原理", "矛盾", "实践", "经济", "政治", "文化", "哲学"),
            ("说明", "体现", "决定", "影响", "因此"),
        ),
        {
            **COMMON_ERRORS,
            "material_mismatch": "材料与原理不匹配",
            "concept_confusion": "概念混淆",
            "logic_error": "逻辑关系错误",
            "analysis_shallow": "材料分析不充分",
        },
    ),
}


def pedagogy_for(subject: str) -> SubjectPedagogy:
    return SUBJECT_PEDAGOGY.get(subject, SUBJECT_PEDAGOGY["数学"])




def _normalize(value: str) -> str:
    return re.sub(r"[\s，。；、,.!?！？:：'\"（）()]", "", value).lower()


def evaluate_teach_back(
    explanation: str,
    subject: str,
    question_type: str,
    knowledge_points: list[Any] | None = None,
    reference_steps: list[str] | None = None,
) -> dict[str, Any]:
    profile = pedagogy_for(subject)
    compact = _normalize(explanation)
    groups = list(profile.teach_back_keywords)
    concepts = [str(item) for item in (knowledge_points or []) if len(str(item)) >= 2]
    references = [str(item) for item in (reference_steps or []) if len(str(item)) >= 2]
    matched_groups = [any(_normalize(word) in compact for word in group) for group in groups]
    matched_concepts = [item for item in concepts[:5] if _normalize(item) in compact]
    has_reasoning = any(
        word in explanation for word in ("因为", "所以", "因此", "说明", "根据", "先", "再", "导致", "体现")
    )
    enough_detail = len(compact) >= 12
    passed = enough_detail and has_reasoning and (all(matched_groups) or bool(matched_concepts))
    missing = []
    if not enough_detail:
        missing.append("讲得再具体一点")
    if not has_reasoning:
        missing.append("补充为什么这样判断")
    if not (all(matched_groups) or matched_concepts):
        missing.append(profile.reasoning_focus)
    feedback = (
        f"讲解清楚：你已经说明了{profile.reasoning_focus}，可以练一道相似题。"
        if passed
        else f"思路已经有了，请再{'，并'.join(missing)}。提示：{profile.teach_back_prompt}"
    )
    return {
        "passed": passed,
        "feedback": feedback,
        "matched_concepts": matched_concepts,
        "reference_count": len(references),
    }
