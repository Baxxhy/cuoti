"""Original deterministic teaching policy, stages and activity projections."""
import copy
import json
from pathlib import Path

from .recognition import short_title

_TEMPLATES = json.loads((Path(__file__).resolve().parents[1] / 'schema/teaching_templates.json').read_text())
_PROGRESS = ['understood','understanding_passed','teach_back','teach_back_passed','near_transfer','far_transfer','next_goal','strategy','branch','mastery_proven','assisted','understanding_index','answer_reveal_acknowledged','targeted_check_pending','transfer_insufficient','question_changed']


def canonical_stage(stage):
    stage = stage.strip(' \t\r\n\v\f')
    for values, target in [(['teach_back','teach_back_retry'],'teach_back'), (['near_transfer','near_remediation'],'near_transfer'), (['far_transfer','transfer_insufficient'],'far_transfer')]:
        if stage in values: return target
    return 'finished' if stage == 'finished' else 'understanding'


def transition(current, event, passed):
    stage = canonical_stage(current)
    if event == 'understanding_advance':
        if stage != 'understanding': raise ValueError('当前不在理解阶段')
        if not passed: raise ValueError('需要先通过理解检查')
        return 'teach_back'
    target = {('teach_back','teach_back_pass'):'near_transfer', ('teach_back','teach_back_fail'):'teach_back', ('near_transfer','near_pass'):'far_transfer', ('near_transfer','near_fail'):'near_transfer', ('far_transfer','far_pass'):'finished', ('far_transfer','far_fail'):'far_transfer'}.get((stage,event))
    if target is None: raise ValueError(f'阶段 {stage} 不能执行事件 {event}')
    return target


def previous_stage(current):
    stage = canonical_stage(current)
    target = {'teach_back':'understanding','near_transfer':'teach_back','far_transfer':'near_transfer'}.get(stage)
    if target is None: raise ValueError(f'阶段 {stage} 不能返回上一步')
    return target


def teaching_policy(kind, has_options, has_working, answer):
    raw = kind.strip().translate(str.maketrans('ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'))
    normalized = {'单选题':'choice','选择题':'choice','multiple-choice':'multiple_choice','多选题':'multiple_choice','填空题':'fill_blank','计算题':'calculation','证明题':'proof','主观题':'subjective'}.get(raw, raw)
    if has_options and normalized in ['other','综合题','']: normalized = 'choice'
    normalized = normalized or 'other'
    reliable = bool(answer.strip())
    compressed = reliable and (normalized in ['choice','multiple_choice','fill_blank'] or not has_working)
    return {'mode':'compressed' if compressed else 'full','question_type':normalized,'show_answer_immediately':reliable,'max_understanding_checks':1 if compressed else 3,'skip_teach_back':compressed,'skip_far_transfer':compressed,'has_working':has_working}


def activity(activity_id, title, question, options=(), answers=(), hint='', teaching=''):
    result = copy.deepcopy(_TEMPLATES['activity_defaults'])
    result.update(id=activity_id,title=title,question=question,options=[{'value':v,'label':label} for v,label in options],correct_answers=list(answers),hint=hint,teaching=teaching)
    return result


def topic(points, kind):
    raw = (points[0] if points else kind or '错题学习').strip()
    return _TEMPLATES['question_type_labels'].get(raw, raw or '错题学习')


def understanding_plan(text, subject, kind, points, references):
    points = [p for p in points if p.strip()]; references = [r for r in references if r.strip()]
    combined = ' '.join([text] + points + references)
    if '正方体' in combined and ('展开图' in combined or '相对面' in combined): return copy.deepcopy(_TEMPLATES['cube_plan'])
    prompt = _TEMPLATES['guided_prompts'].get(subject, _TEMPLATES['guided_prompts']['数学'])
    label = points[0] if points else topic([],kind)
    reference = references[0] if references else prompt
    summary = reference if '$' in reference or '\\' in reference else short_title(reference,42)
    return [activity('understanding-1',f'先抓住{label}','完成这道题时，第一步最应该关注什么？',[('key',label),('answer','只记住最后答案'),('skip','跳过题目条件直接计算')],['key'],f'先回到题目条件，找到与{label}直接相关的信息。',f'这道题先围绕“{label}”判断，再继续后面的步骤。'), activity('understanding-2','确认下一步做法','下面哪种做法更合适？',[('reference',summary),('guess','不看条件，凭印象猜一个答案')],['reference'],prompt,f'关键做法是：{reference}')]


def public_activity(source, attempt, feedback='', teaching=''):
    result = {k:source[k] for k in ['id','type','title','question']}
    result.update(options=source.get('options',[]),keywords=source.get('keywords',[]),visual=source.get('visual',{}),attempt=attempt,max_attempts=2,feedback=feedback,teaching=teaching or source.get('teaching',''))
    for key in ['teaching_title','sentence_starter','input_mode','variant_id']:
        if key in source: result[key]=source[key]
    return {k:v for k,v in result.items() if k in ['options','keywords','visual'] or v is not None and v != ''}


def public_progress(state):
    return {k:copy.deepcopy(state[k]) for k in _PROGRESS if k in state}


def knowledge(value):
    return (value.get('analysis') or {}).get('knowledge_points') or value['question']['knowledge_points']


def visualization(subject, kind, points):
    text = ' '.join([subject,kind]+points).lower()
    pairs=[('勾股|直角三角形','right_triangle'),('圆周角|圆心角|圆','circle'),('坐标|中点|两点距离','coordinate_geometry'),('三角形|全等|相似','triangle'),('二次函数|抛物线','quadratic_function'),('一次函数|直线函数','linear_function'),('方程|等式|移项','equation_balance'),('匀加速|速度时间|v-t','uniform_acceleration'),('抛体|平抛|斜抛','projectile_motion'),('匀速|路程|s=vt','uniform_motion'),('受力|合力|支持力','force_diagram'),('机械能|动能|势能|功与能','work_energy'),('压强|压力','pressure'),('浮力|排液','buoyancy'),('时间轴|年代|先后顺序','history_timeline'),('时空|传播|地图','timeline_map')]
    return next((visual for words, visual in pairs if any(w in text for w in words.split('|'))), None)


def choice_answer(answer, options):
    text = answer.strip(); chars = text.translate(str.maketrans('abcdefghijklmnopqrstuvwxyz','ABCDEFGHIJKLMNOPQRSTUVWXYZ'))
    selected = ''
    for index, char in enumerate(chars):
        if char not in 'ABCDEFGH': continue
        if index > 0 and chars[index-1] in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' or index+1 < len(chars) and chars[index+1] in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ': continue
        if any(o['label'].strip().upper() == char for o in options): selected += char
    if selected: return selected
    compact = ''.join(text.split())
    for option in options:
        if compact and compact == ''.join(option['text'].split()): return option['label'].strip().upper()
    return text


def initial_state(value, policy, brief):
    question, analysis = value['question'], value['analysis']; points = knowledge(value)
    state = {'understood':False,'understanding_passed':False,'teach_back':None,'near_transfer':None,'far_transfer':None,'next_goal':'完成一个小问题','strategy':'micro_activity','branch':'opening','mastery_proven':False,'last_message':'','repeated_count':0,'assisted':False,'understanding_index':0,'activity_attempts':{},'activity_feedback':'','answer_reveal_acknowledged':False,'targeted_check_pending':False}
    state.update(teaching_policy=policy,teaching_brief=brief,subject=question['subject'],question_type=question['question_type'],visualization_type=visualization(question['subject'],question['question_type'],question['knowledge_points']),understanding_plan=[] if isinstance(brief,dict) else understanding_plan(question['question_text'],question['subject'],question['question_type'],points,[r['text'] for r in value['references']]))
    raw = question['student_answer'] or ''; student = raw or '未作答'
    if isinstance(brief,dict):
        if policy['question_type'] in ['choice','multiple_choice']: student = choice_answer(raw,question['options'])
        reveal = {k:brief[k] for k in ['topic','correct_answer','key_explanation','option_explanations']}
    else: reveal = {'topic':topic(points,question['question_type']),'correct_answer':analysis['final_answer'].strip(),'key_explanation':'','option_explanations':[]}
    reveal['student_answer'] = student; state['answer_reveal']=reveal
    return state
