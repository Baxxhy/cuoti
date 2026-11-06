"""Native task limits and visualization admission, ported from the original service."""
import copy
import json
import time
from fastapi import HTTPException


class TaskBudgetExceeded(Exception):
    def __init__(self,stage):
        super().__init__('本次执行已到时限，结果未提交');self.stage=stage


class TaskBudget:
    def __init__(self,started=None,limit=45,clock=time.monotonic):
        self.clock=clock;self.started=clock() if started is None else started;self.limit=limit

    def elapsed_ms(self):return int((self.clock()-self.started)*1000)
    def remaining(self):return self.limit-(self.clock()-self.started)
    def check(self,stage):
        if self.remaining()<=0:raise TaskBudgetExceeded(stage)
    def timeout_seconds(self,cap,reserve_seconds=0):
        seconds=int(self.remaining())-reserve_seconds
        if seconds<1:raise TaskBudgetExceeded('remaining_budget')
        return min(seconds,cap)


def object_value(value,key):
    result=value.get(key)
    return result if isinstance(result,dict) else {}


def integer_value(value,key):
    result=value.get(key)
    return result if type(result) is int else 0


def at_limit(task):
    return integer_value(task,'run_count')>=72 or integer_value(object_value(task,'checkpoint'),'rounds')>=24


def stopped_view(message):
    return {'title':message,'prompt_blocks':[],'input_kind':'none','primary_action':'','secondary_actions':[],'feedback':message}


def limit_view():
    return {**stopped_view('已到本次学习上限。结束后可从原题重开，记录会保留。'),'title':'本次先停在这里'}


def stop_at_limit(db,task,reason):
    recoverable=reason=='prepare_budget'
    view=stopped_view('准备耗时较长，内容已保留，可以稍后继续') if recoverable else limit_view()
    if recoverable:
        view['secondary_actions']=['resume'];photo=object_value(object_value(task,'student_view'),'handwriting')
        if photo:view['handwriting']=copy.deepcopy(photo)
    db.query("UPDATE learning_tasks SET status='failed',version=version+1,student_view=?,exit_reason=?,lease_token=NULL,lease_until=NULL,updated_at=UTC_TIMESTAMP(6) WHERE id=?",[json.dumps(view,ensure_ascii=False),reason,task['id']])
    db.query("UPDATE learning_task_actions SET status='failed',updated_at=UTC_TIMESTAMP(6) WHERE task_id=? AND status='pending'",[task['id']])


def visual_values(body):
    raw=body.get('visual_values',{})
    if not isinstance(raw,dict):raise HTTPException(422,'图示参数格式不正确')
    if len(raw)>3:raise HTTPException(422,'图示参数过多')
    result={}
    for key,value in raw.items():
        if key not in ['delta','k','b','a','h'] or type(value) not in [int,float]:raise HTTPException(422,'包含不支持的图示参数')
        if not -100000000<=value<=100000000:raise HTTPException(422,'图示参数超出范围')
        result[key]=float(value)
    return result


def validate_visual_action(task,body,kind,values):
    if kind!='observe_visualization' and 'visual_values' in body:raise HTTPException(422,'当前动作不接受图示参数')
    if kind=='visualize' and object_value(task,'student_view').get('input_kind')!='text':raise HTTPException(409,'请先核对原题再查看图示')
    if kind not in ['observe_visualization','close_visualization']:return
    state=object_value(task,'checkpoint');visual=object_value(state,'visualization')
    if state.get('visual_open') is not True or not visual or visual.get('source_phase','')!=state.get('phase',''):raise HTTPException(409,'当前没有可操作的图示，请先打开')
    if kind!='observe_visualization':return
    variables=object_value(visual,'spec').get('interactive_variables') or []
    if len(values)!=len(variables):raise HTTPException(422,'图示参数与当前图示不匹配')
    for variable in variables:
        name=variable['name']
        if name not in values:raise HTTPException(422,'图示参数与当前图示不匹配')
        number=values[name];low=float(variable['min']);high=float(variable['max']);step=float(variable['step'])
        if step<=0 or number<low or number>high:raise HTTPException(422,'图示参数超出范围')
        grid=(number-low)/step;difference=grid-int(grid+.5)
        if difference < -0.0000001 or difference > 0.0000001:raise HTTPException(422,'图示参数不符合当前步长')
