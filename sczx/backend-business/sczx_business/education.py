"""Subject-neutral curriculum vocabulary; content and decisions remain versioned in JSON snapshots."""
import copy,json,re,unicodedata
from pathlib import Path
CATALOG=json.loads((Path(__file__).parent/'prompts'/'subjects.json').read_text())
RESPONSE_TYPES=[{'value':value,'label':label} for value,label in [('short_answer','简答'),('single_choice','单选'),('multiple_choice','多选'),('true_false','判断'),('fill_blank','填空'),('essay','论述'),('calculation','计算'),('proof','证明'),('reading','阅读'),('writing','写作'),('translation','翻译'),('experiment','实验分析'),('programming','程序与算法')]]
RESPONSE_IDS={x['value'] for x in RESPONSE_TYPES}
GRADES=['七年级','八年级','九年级','高一','高二','高三']
def catalog():return {'stages':[{'value':'junior','label':'初中','grades':GRADES[:3]},{'value':'senior','label':'高中','grades':GRADES[3:]}],'subjects':[{'value':x['name'],'label':x['name'],'stages':x['stages']} for x in CATALOG['subjects']],'responseTypes':copy.deepcopy(RESPONSE_TYPES),'gradingModes':[{'value':'manual','label':'教师评阅'},{'value':'exact','label':'参考答案匹配'},{'value':'math','label':'数学表达式核对'}]}
def context_subject(data):
    context=data.get('context') or {};lesson=context.get('lesson') or data.get('lesson') or {};question=context.get('question') or data.get('questionData') or {}
    subject=lesson.get('subject') or context.get('subject') or data.get('subject') or question.get('subject') or ''
    grade=lesson.get('grade') or context.get('grade') or data.get('grade') or question.get('grade') or ''
    return str(subject).strip(),str(grade).strip()
def profile(subject):return next((x for x in CATALOG['subjects'] if subject==x['name']),None) or next((x for x in CATALOG['subjects'] if subject in x.get('aliases',[])),None)
def is_mathematical(subject):return subject in ('数学','math','mathematics')
def response_type(question):return question.get('responseType') or ('calculation' if question.get('equation') else 'short_answer')
def grading_mode(question):
    if question.get('gradingMode') in ('manual','exact','math'):return question['gradingMode']
    if response_type(question) in ('single_choice','multiple_choice','true_false'):return 'exact'
    return 'math' if question.get('equation') else 'manual'
def question_errors(q):
    errors=[];kind=response_type(q);mode=grading_mode(q)
    if kind not in RESPONSE_IDS:errors.append('请选择有效题型')
    if q.get('gradingMode') and q['gradingMode'] not in ('manual','exact','math'):errors.append('核对方式无效')
    if not isinstance(q.get('prompt'),str) or not q['prompt'].strip():errors.append('请填写题干')
    if not str(q.get('answer','')).strip():errors.append('请填写参考答案或评价要点')
    if kind in ('single_choice','multiple_choice'):
        opts=q.get('options') or []
        if not isinstance(opts,list) or len(opts)<2 or len(opts)>12 or any(not isinstance(o,dict) or not str(o.get('id','')).strip() or not str(o.get('text','')).strip() for o in opts):errors.append('选择题需要2至12个有编号和内容的选项')
        else:
            ids=[str(o['id']) for o in opts]
            if len(ids)!=len(set(ids)):errors.append('选项编号不能重复')
            values=answer_parts(q.get('answer','')) if kind=='multiple_choice' else [str(q.get('answer','')).strip()]
            if not values or any(v not in ids for v in values):errors.append('参考答案必须使用实际选项编号')
    if kind=='true_false' and str(q.get('answer','')).strip() not in ('true','false','正确','错误','对','错'):errors.append('判断题参考答案应为正确或错误')
    if mode=='math' and not str(q.get('equation','')).strip():errors.append('数学核对需要填写表达式；其他题目可选择教师评阅')
    if mode=='exact' and kind in ('essay','writing','proof','experiment','programming','reading'):errors.append('该开放题型应采用教师评阅')
    return errors
def answer_parts(value):return sorted(set(x for x in re.split(r'[,，、;；\s]+',str(value).strip()) if x))
def normalized_answer(value,case_sensitive=True):
    value=unicodedata.normalize('NFKC',str(value)).strip()
    return value if case_sensitive else value.casefold()
def assess_general(answer,question):
    mode=grading_mode(question);kind=response_type(question)
    if mode=='manual':return {'status':'unverified','correct':False,'scope':'主观答案与过程由教师依据评价要点评阅','message':'作答已保存，等待教师评阅。','requiresTeacherReview':True}
    if mode=='math':
        from .grading import assess
        result=assess(answer,question.get('answer',''),question.get('equation',''))
        result['message']='参考表达式已核对，解题过程仍需结合题意检查。' if result['correct'] else '该表达式需要进一步核对。' if result['status']=='unverified' else '请检查题目条件与计算过程。'
        return result
    expected=question.get('answer','');values=question.get('acceptedAnswers') or [expected]
    if not isinstance(values,list):values=[expected]
    if kind=='multiple_choice':equal=answer_parts(answer)==answer_parts(expected)
    elif kind=='true_false':
        boolean=lambda v:{'正确':'true','对':'true','错误':'false','错':'false'}.get(str(v).strip(),str(v).strip().lower())
        equal=boolean(answer)==boolean(expected)
    else:equal=any(normalized_answer(answer,question.get('caseSensitive',True))==normalized_answer(v,question.get('caseSensitive',True)) for v in values)
    return {'status':'verified' if equal else 'inconsistent','correct':equal,'scope':'教师配置的客观参考答案匹配','message':'答案与参考答案一致。' if equal else '答案与参考答案不一致，请复查。'}
def linear_context(data):
    subject,_=context_subject(data);ctx=data.get('context') or {};q=ctx.get('question') or {};equation=str(q.get('equation') or data.get('confirmedEquation') or '')
    title=str((ctx.get('lesson') or data.get('lesson') or {}).get('title',''))
    if subject and not is_mathematical(subject):return False
    if not equation:return bool(re.search('一元一次|等式性质',title))
    from .math_tools import solve_text_equation,parse_math_expression
    import sympy as sp
    try:
        solved,valid=solve_text_equation(equation)
        if not valid:return False
        l,r=equation.split('=');expr=parse_math_expression(l)-parse_math_expression(r)
        return len(expr.free_symbols)==1 and sp.Poly(expr,next(iter(expr.free_symbols))).degree()==1
    except Exception:return False
