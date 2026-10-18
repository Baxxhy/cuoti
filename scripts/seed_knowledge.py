#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db import SessionLocal
from app.models import KnowledgePoint, KnowledgeRelation

TOPICS = {
    "数学": [
        ("number_rational", "有理数运算", "数与式", "a-b=a+(-b)", "equation_balance"),
        ("algebra_expression", "整式与代数式", "数与式", "ax+b", "equation_balance"),
        ("equation_property", "等式基本性质", "方程", "a=b ⇒ a+c=b+c", "equation_balance"),
        ("linear_equation", "一元一次方程", "方程", "ax+b=0", "equation_balance"),
        ("transpose", "移项与符号", "方程", "x+a=b ⇒ x=b-a", "equation_balance"),
        ("bracket", "去括号法则", "方程", "-(a+b)=-a-b", "equation_balance"),
        ("inequality", "一元一次不等式", "不等式", "ax>b", "linear_function"),
        ("coordinate", "平面直角坐标系", "函数", "P(x,y)", "coordinate_geometry"),
        ("linear_function", "一次函数", "函数", "y=kx+b", "linear_function"),
        ("quadratic_function", "二次函数", "函数", "y=a(x-h)^2+k", "quadratic_function"),
        ("parameter_discussion", "参数讨论", "函数", "按参数临界值分类", "quadratic_function"),
        ("boundary_condition", "边界条件", "函数", "临界值必须单独检验", "quadratic_function"),
        ("vertex_translation", "抛物线顶点与平移", "函数", "顶点(h,k)", "quadratic_function"),
        ("function_image", "函数图像判读", "函数", "x↦y", "linear_function"),
        ("triangle", "三角形基本关系", "几何", "a+b>c", "triangle"),
        ("right_triangle", "直角三角形", "几何", "∠C=90°", "right_triangle"),
        ("pythagorean", "勾股定理", "几何", "a²+b²=c²", "right_triangle"),
        ("congruence", "全等三角形", "几何", "SSS/SAS/ASA", "triangle"),
        ("similarity", "相似三角形", "几何", "a₁/a₂=b₁/b₂", "triangle"),
        ("circle_basic", "圆的基本性质", "圆", "C=2πr", "circle"),
        ("circle_angle", "圆周角与圆心角", "圆", "圆周角=圆心角/2", "circle"),
        ("tangent", "切线性质", "圆", "半径⊥切线", "circle"),
        ("statistics_mean", "平均数与加权平均", "统计", "x̄=Σx/n", "coordinate_geometry"),
        ("probability", "简单概率", "概率", "P(A)=m/n", "coordinate_geometry"),
        ("factorization", "因式分解", "数与式", "a²-b²=(a-b)(a+b)", "equation_balance"),
        ("fraction", "分式方程", "方程", "a/x=b", "equation_balance"),
        ("radical", "二次根式", "数与式", "√(a²)=|a|", "right_triangle"),
        ("quadratic_equation", "一元二次方程", "方程", "ax²+bx+c=0", "quadratic_function"),
        ("trigonometry", "锐角三角函数", "几何", "sinA=对边/斜边", "right_triangle"),
        ("vector", "向量与方向", "几何", "AB⃗=(x₂-x₁,y₂-y₁)", "coordinate_geometry"),
        ("sequence", "数列规律", "代数", "aₙ=a₁+(n-1)d", "linear_function"),
        ("proof", "数学推理与证明", "综合", "条件⇒结论", "triangle"),
    ],
    "物理": [
        ("unit", "物理量与单位", "测量", "量值=数值×单位", "uniform_motion"),
        ("uniform_motion", "匀速直线运动", "运动", "v=s/t", "uniform_motion"),
        ("acceleration", "加速度", "运动", "a=Δv/Δt", "uniform_acceleration"),
        ("uniform_acceleration", "匀加速直线运动", "运动", "v=v₀+at", "uniform_acceleration"),
        ("motion_graph", "运动图像", "运动", "斜率表示速度或加速度", "uniform_acceleration"),
        ("projectile", "抛体运动", "运动", "x=v₀t", "projectile_motion"),
        ("force", "力与受力分析", "力学", "力有大小方向作用点", "force_diagram"),
        ("force_object", "受力对象", "力学", "先隔离研究对象再画受力图", "force_diagram"),
        ("newton_first", "牛顿第一定律", "力学", "ΣF=0⇒状态不变", "force_diagram"),
        ("newton_second", "牛顿第二定律", "力学", "F=ma", "force_diagram"),
        ("friction", "摩擦力", "力学", "f=μN", "force_diagram"),
        ("gravity", "重力", "力学", "G=mg", "force_diagram"),
        ("work", "功", "功和能", "W=Fs", "work_energy"),
        ("power", "功率", "功和能", "P=W/t", "work_energy"),
        ("kinetic_energy", "动能", "功和能", "Eₖ=mv²/2", "work_energy"),
        ("energy_conservation", "机械能守恒", "功和能", "Eₖ+Eₚ=常量", "work_energy"),
        ("pressure", "压强", "压强", "p=F/S", "pressure"),
        ("liquid_pressure", "液体压强", "压强", "p=ρgh", "pressure"),
        ("buoyancy", "浮力", "浮力", "F浮=ρ液gV排", "buoyancy"),
        ("circuit", "欧姆定律", "电学", "I=U/R", "linear_function"),
        ("electric_power", "电功率", "电学", "P=UI", "work_energy"),
    ],
    "历史": [
        ("chronology", "历史时间线", "史学方法", "先后顺序", "history_timeline"),
        ("causality", "直接原因与根本原因", "史学方法", "触发事件≠深层动力", "history_timeline"),
        ("background", "背景、条件与原因", "史学方法", "条件促进但不等于原因", "history_timeline"),
        ("material", "史料实证", "史学方法", "论点必须有史料支撑", "timeline_map"),
        ("comparison", "历史比较", "史学方法", "同中求异、异中求同", "history_timeline"),
        ("ancient_china", "中国古代制度演变", "中国古代史", "制度随社会结构演变", "history_timeline"),
        ("unification", "统一多民族国家", "中国古代史", "统一与治理", "timeline_map"),
        ("industrial_revolution", "工业革命", "世界近代史", "技术—生产—社会", "history_timeline"),
        ("modernization", "近代化探索", "中国近代史", "器物—制度—思想", "history_timeline"),
        ("revolution", "革命与社会变迁", "世界近代史", "矛盾积累与触发", "timeline_map"),
        ("war", "战争原因与影响", "世界史", "短期冲突与长期格局", "timeline_map"),
        ("reform", "改革的条件与成效", "综合", "生产关系适应生产力", "history_timeline"),
        ("diplomacy", "国际关系格局", "世界现代史", "力量对比影响格局", "timeline_map"),
        ("economy_society", "经济与社会生活", "综合", "经济基础影响社会", "history_timeline"),
        ("evaluation", "历史人物与事件评价", "史学方法", "置于时代并一分为二", "history_timeline"),
    ],
    "英语": [
        ("relative_clause", "定语从句", "语法", "先行词+关系词+从句", "knowledge_graph"),
    ],
    "化学": [
        ("ionic_equation", "离子方程式", "离子反应", "可拆物质写离子，不可拆物质保留化学式", "equation_balance"),
    ],
}

# 面向初一至高三的课程骨架。每个主题都会生成可检索知识卡，供诊断和教学Agent按年级调用。
GRADE_TOPICS = {
    "语文": {
        "初一": ["记叙文要素与线索", "人物描写与形象", "古诗文朗读与实词"], "初二": ["说明方法与作用", "新闻与非连续文本", "文言文句式与翻译"],
        "初三": ["议论文论点论据论证", "小说情节与主旨", "中考作文审题立意"], "高一": ["文学阅读证据链", "文言实词虚词", "议论文结构与论证"],
        "高二": ["诗歌意象与手法", "小说叙事视角", "语言文字运用"], "高三": ["信息类文本推断", "古诗文综合鉴赏", "高考作文任务驱动"],
    },
    "数学": {
        "初一": ["有理数与代数式", "一元一次方程", "几何图形初步"], "初二": ["全等三角形", "一次函数", "整式乘除与因式分解"],
        "初三": ["一元二次方程", "二次函数", "圆与锐角三角函数"], "高一": ["集合与逻辑", "函数性质", "三角函数"],
        "高二": ["数列", "立体几何", "圆锥曲线"], "高三": ["导数综合", "概率统计", "解析几何综合"],
    },
    "英语": {
        "初一": ["一般现在时", "名词代词与冠词", "基础阅读定位"], "初二": ["过去时与比较级", "宾语从句基础", "语篇主旨与细节"],
        "初三": ["被动语态", "定语从句基础", "中考写作结构"], "高一": ["时态语态综合", "非谓语动词基础", "阅读推断"],
        "高二": ["定语从句与名词性从句", "非谓语动词综合", "应用文写作"], "高三": ["语篇衔接", "完形逻辑", "读后续写"],
    },
    "物理": {
        "初一": ["科学测量与实验", "运动描述入门", "声光现象入门"], "初二": ["机械运动", "质量密度", "力与运动"],
        "初三": ["压强浮力", "功和机械能", "电路与电功率"], "高一": ["运动学", "相互作用", "牛顿运动定律"],
        "高二": ["电场与电路", "磁场与电磁感应", "机械振动与波"], "高三": ["动量与能量综合", "电磁综合", "实验与图像分析"],
    },
    "化学": {
        "初一": ["物质变化观察", "实验安全与仪器", "微粒观念入门"], "初二": ["空气水与溶液", "元素与化学式", "质量守恒"],
        "初三": ["化学方程式", "酸碱盐", "常见气体实验"], "高一": ["物质的量", "离子反应", "氧化还原反应"],
        "高二": ["化学反应原理", "有机化学基础", "物质结构与性质"], "高三": ["化学实验综合", "工艺流程", "平衡与计算综合"],
    },
    "生物": {
        "初一": ["细胞结构", "生物体结构层次", "绿色植物生活"], "初二": ["人体生理", "动物行为", "遗传与进化基础"],
        "初三": ["生态系统", "健康与免疫", "生物实验探究"], "高一": ["分子与细胞", "细胞代谢", "细胞生命历程"],
        "高二": ["遗传规律", "稳态与调节", "生态系统"], "高三": ["实验设计", "遗传综合", "生物技术与工程"],
    },
    "历史": {
        "初一": ["中国古代国家形成", "统一多民族国家", "古代经济文化"], "初二": ["中国近代化探索", "民族危机与抗争", "新民主主义革命"],
        "初三": ["世界古代文明", "工业革命与资本主义", "世界战争与格局"], "高一": ["中外历史纲要", "国家制度与社会治理", "经济与社会生活"],
        "高二": ["文化交流与传播", "战争与和平", "史料实证方法"], "高三": ["中外历史比较", "历史因果综合", "材料论证与评价"],
    },
    "地理": {
        "初一": ["地图与地球", "世界气候与居民", "世界区域地理"], "初二": ["中国自然环境", "中国经济与区域", "乡土地理"],
        "初三": ["区域比较", "图表综合判读", "人地协调"], "高一": ["地球运动", "大气与水循环", "地貌与植被"],
        "高二": ["人口城市产业", "区域发展", "资源环境安全"], "高三": ["自然地理过程", "人文区位综合", "区域可持续发展"],
    },
    "道德与法治": {
        "初一": ["成长与友谊", "集体生活", "生命与规则"], "初二": ["社会责任", "权利与义务", "法治与国家制度"],
        "初三": ["富强创新", "民主法治", "文明与共同体"], "高一": ["公民与法治衔接", "社会参与", "规则意识"],
        "高二": ["权利义务综合", "社会责任实践", "法治案例分析"], "高三": ["材料观点综合", "公共参与", "规范表达"],
    },
    "思想政治": {
        "初一": ["生活中的规则", "个人与集体", "责任意识"], "初二": ["公民权利义务", "法治观念", "国家制度基础"],
        "初三": ["国家发展", "文化自信", "世界与中国"], "高一": ["中国特色社会主义", "经济与社会", "政治与法治"],
        "高二": ["哲学与文化", "法律与生活", "逻辑与思维"], "高三": ["经济政治综合", "哲学材料分析", "选择性必修综合"],
    },
}


def card_content(subject: str, index: int, name: str, chapter: str, formula: str, visualization: str, previous: str | None, following: str | None) -> dict:
    return {
        "grade": "初中",
        "chapter": chapter,
        "definition": f"{name}是{subject}中用于解释和解决“{chapter}”问题的核心知识。",
        "formulas": [formula] if formula else [],
        "prerequisites": [previous] if previous else [],
        "common_misconceptions": [f"只记住{name}的结论，却忽略适用条件", "混淆相近概念或因果层级"],
        "teaching_prompts": [f"先说出{name}的适用条件", "用一个反例检查当前理解", "把规则迁移到新情境"],
        "worked_example": f"示例：识别题目条件，选择{name}，写出依据“{formula}”，再检查结论。",
        "visualization_types": [visualization],
        "related_knowledge": [value for value in (previous, following) if value],
        "sequence": index,
    }


async def seed() -> None:
    async with SessionLocal() as db:
        stored: dict[str, KnowledgePoint] = {}
        for subject, topics in TOPICS.items():
            for index, (slug, name, chapter, formula, visualization) in enumerate(topics):
                code = f"{subject.lower()}.{slug}" if subject != "数学" else f"math.{slug}"
                previous = topics[index - 1][1] if index else None
                following = topics[index + 1][1] if index + 1 < len(topics) else None
                content = card_content(subject, index, name, chapter, formula, visualization, previous, following)
                item = (await db.scalars(select(KnowledgePoint).where(KnowledgePoint.code == code))).first()
                if item is None:
                    item = KnowledgePoint(code=code, subject=subject, name=name, content=content)
                    db.add(item); await db.flush()
                else:
                    item.subject, item.name, item.content = subject, name, content
                stored[code] = item
        for subject, grades in GRADE_TOPICS.items():
            for grade, topics in grades.items():
                for index, name in enumerate(topics):
                    code = f"curr.{subject}.{grade}.{index + 1}"
                    content = {
                        "grade": grade, "chapter": name,
                        "definition": f"{name}是{grade}{subject}的核心学习主题，作答时要结合题目条件和本学科证据。",
                        "formulas": [], "prerequisites": [topics[index - 1]] if index else [],
                        "common_misconceptions": [f"只记住{name}的结论，没有结合题目证据", "混淆相近概念或适用条件"],
                        "teaching_prompts": ["先提取题目条件或材料证据", f"说明{name}如何支持结论", "用新情境重新验证"],
                        "worked_example": f"示例步骤：识别题目要求—调用{name}—写出依据—形成规范结论。",
                        "visualization_types": [], "related_knowledge": topics, "sequence": index,
                    }
                    item = (await db.scalars(select(KnowledgePoint).where(KnowledgePoint.code == code))).first()
                    if item is None:
                        item = KnowledgePoint(code=code, subject=subject, name=name, content=content)
                        db.add(item); await db.flush()
                    else:
                        item.subject, item.name, item.content = subject, name, content
                    stored[code] = item
        await db.flush()
        for subject, topics in TOPICS.items():
            prefix = "math" if subject == "数学" else subject.lower()
            for index in range(1, len(topics)):
                source, target = stored[f"{prefix}.{topics[index][0]}"], stored[f"{prefix}.{topics[index - 1][0]}"]
                relation = (await db.scalars(select(KnowledgeRelation).where(
                    KnowledgeRelation.source_id == source.id, KnowledgeRelation.target_id == target.id,
                    KnowledgeRelation.relation_type == "prerequisite",
                ))).first()
                if relation is None:
                    db.add(KnowledgeRelation(source_id=source.id, target_id=target.id, relation_type="prerequisite"))
        await db.commit()
        curriculum_count = sum(len(topics) for grades in GRADE_TOPICS.values() for topics in grades.values())
        print(f"knowledge_cards={sum(len(value) for value in TOPICS.values()) + curriculum_count} curriculum_cards={curriculum_count}")


if __name__ == "__main__":
    asyncio.run(seed())
