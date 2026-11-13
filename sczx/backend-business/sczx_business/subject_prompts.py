"""Versioned, subject-routed prompts shared by CLI and API providers."""
from pathlib import Path
from .education import context_subject,profile,linear_context
ROOT=Path(__file__).parent/'prompts'
def instruction(data):
    subject,grade=context_subject(data);selected=profile(subject)
    result=(ROOT/'general.md').read_text()+f'\n当前学科：{subject or "待确认"}；年级：{grade or "待确认"}。\n'
    result+=selected['instruction'] if selected else '使用材料所对应学科的方法；没有适用学科资料时说明缺项并提出确认问题。'
    if linear_context(data):result+='\n'+(ROOT/'linear_equation.md').read_text()
    if data.get('remediation') or data.get('examCandidate'):
        result+='\nresponseType必须使用题型英文标识：short_answer/single_choice/multiple_choice/true_false/fill_blank/essay/calculation/proof/reading/writing/translation/experiment/programming；gradingMode仅为manual/exact/math。选项使用{id,text}；非选择题options为空数组。'
    if data.get('remediation'):
        result+='\n只处理wrongId对应原题。analysis的evidence逐字来自originalAnswer或originalReason；错因作为建议。variant生成与原知识目标相关的新题：非方程题equation留空，提供prompt、expected、responseType、gradingMode、options和rationale。开放题gradingMode为manual，参考答案是评价要点，不能声称已程序判对。相关新题必须自编另一段材料或更换具体情境，保留原学习目标；不能只改写原问题，不复用原片段的人物动作。独立复测不附提示，不复用已生成题干。'
    if data.get('guidance'):result+='\n必须依据context.difficultyAssessment与experienceDecision调整指导。possibleCauses为空代表原因未确定，先用confirmationQuestion追问。只有selected中的版本可当作已审核经验；fallback时明确说明使用通用指导，不编造教师或来源。steps应具体采用已选method；学习记忆仅作已有事实，不作长期能力标签。'
    if data.get('guidance'):result+='\n每轮hint简短、steps最多3步、一个具体追问；representation可为question/numeric/balance/symbolic/comparison/text/example/evidence/diagram，仅选择符合本科目的方式。usedCaseVersionIds只引用实际给出的版本，prerequisiteId无依据留空。'
    if data.get('experienceDecision'):result+='\nexperienceDecision给出经审核的教法候选及来源类型；在活动中具体采用selected.method，并注明团队自编、公开材料或教师提供的实际来源，不改写成名师背书。fallback时只按课时生成，不声称引用了教学经验。'
    if data.get('examCandidate'):result+='\n生成待教师审核的候选题；按实际题型返回选项、参考答案、解析与评分方式，非数学题equation留空，不标成已经审核。'
    return result
