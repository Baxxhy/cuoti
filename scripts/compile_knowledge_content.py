"""Compile project-authored knowledge summaries without changing card IDs or relations."""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "backend-cangjie/schema"
MISCONCEPTIONS = {
    "移项与符号": ["把未移动的项也变号", "移项后没有改变被移动项的符号"],
    "去括号法则": ["括号前为减号时只改变第一项符号", "系数没有乘到括号内每一项"],
    "二次根式": ["忽略根号内非负的适用条件", "把√(a²)无条件写成a而不是|a|"],
    "一元一次不等式": ["同除以负数后没有改变不等号方向"],
    "全等三角形": ["把两边及非夹角相等当作一般全等判定"],
    "平均数与加权平均": ["样本量不同时直接平均两个组的平均数"],
    "加速度": ["把速度大理解为加速度一定大"],
    "受力对象": ["把作用在不同物体上的力画在同一受力图中抵消"],
    "离子方程式": ["配平原子后没有检查电荷守恒"],
    "历史时间线": ["用事件先后顺序直接证明因果关系"],
    "定语从句": ["只看先行词，忽略关系词在从句中承担的成分"],
}
EXAMPLES = {
    "有理数与代数式": "当a=−2时，a²=4，而−a²=−4。负号是否被括号括住会改变运算顺序，不能把两者看成相同表达式。",
    "一元一次方程": "解2x+3=11：两边减3得2x=8，再同除以2得x=4。代回原式：2×4+3=11。",
    "移项与符号": "3x−2=7，两边加2得3x=7+2，因此x=3。移动的是−2，等式右边原有的7不变号。",
    "去括号法则": "−2(x−3)=−2x+6，因为−2既要乘x，也要乘−3。",
    "一元一次不等式": "−2x<6，两边同除以−2时不等号反向，得到x>−3。",
    "因式分解": "x²−9是平方差，分解为(x−3)(x+3)。展开可检查中间项相消。",
    "二次根式": "当a=−3时，√(a²)=√9=3=|a|，不能写成−3。",
    "平均数与加权平均": "一组2人的平均分是80，另一组3人的平均分是90，总平均分=(2×80+3×90)/5=86。",
    "一般现在时": "She plays tennis. 改为一般疑问句：Does she play tennis? 使用does后，play用原形。",
    "历史时间线": "某项改革后出现经济增长，只能先确认时间先后；还需材料说明改革怎样影响生产，才能支持因果解释。",
}


def compile_content(check=False):
    path = ROOT / "knowledge_seed.json"
    data = json.loads(path.read_text())
    explanations = json.loads((ROOT / "knowledge_explanations.json").read_text())
    for card in data["cards"]:
        content = card["content"]
        content["definition"] = explanations[card["name"]]
        # Remove earlier generated scaffolding; a generic process is not an example.
        content["worked_example"] = EXAMPLES.get(card["name"], "")
        content["common_misconceptions"] = MISCONCEPTIONS.get(card["name"], [])
        content["teaching_prompts"] = []
        content["content_origin"] = "项目编写的知识提要，非教材原文"
        content["grade_note"] = "年级仅供检索参考，不同教材进度可能不同"
    expected = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if check:
        if path.read_text() != expected:
            raise SystemExit("知识提要与导入文件不同步，请运行 scripts/compile_knowledge_content.py")
    else:
        path.write_text(expected)
    print(f"知识提要同步：{len(data['cards'])} 张；保留知识编号与关系")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    compile_content(parser.parse_args().check)
