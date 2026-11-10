"""Fixed, bounded VisualizationSpec. No model-supplied executable content."""
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,model_validator
class BalanceState(BaseModel):
    model_config=ConfigDict(extra='forbid')
    left:float=Field(ge=0,le=10000,allow_inf_nan=False,strict=True)
    right:float=Field(ge=0,le=10000,allow_inf_nan=False,strict=True)
class VisualizationSpec(BaseModel):
    model_config=ConfigDict(extra='forbid')
    version:Literal[1]=1
    type:Literal['balance','equality_operations']='balance'
    initial:BalanceState
    actions:list[Literal['left_add','right_add','both_add','left_subtract','right_subtract','both_subtract','reset']]=Field(min_length=1,max_length=7)
    step:float=Field(gt=0,le=100,allow_inf_nan=False,strict=True)
    minimum:float=Field(default=0,ge=0,le=10000,allow_inf_nan=False,strict=True)
    maximum:float=Field(default=100,ge=1,le=10000,allow_inf_nan=False,strict=True)
    learningGoal:str=Field(min_length=1,max_length=1000)
    completion:Literal['balanced_with_explanation']='balanced_with_explanation'
    @model_validator(mode='after')
    def bounds(self):
        if self.minimum>=self.maximum or any(not self.minimum<=v<=self.maximum for v in (self.initial.left,self.initial.right)):raise ValueError('初始状态超出数值边界')
        return self

def specification(config):
    if 'initial' in config:return VisualizationSpec.model_validate(config).model_dump()
    if set(config)-{'type','base','step','max'}:raise ValueError('天平含不支持的参数')
    from math import isfinite
    base,step,maximum=(config.get(k) for k in ('base','step','max'))
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not isfinite(v) for v in (base,step,maximum)) or base<0 or step<=0 or not 1<=maximum<=100:raise ValueError('旧天平参数无效')
    return VisualizationSpec(initial=BalanceState(left=base,right=base),step=step,maximum=base+step*maximum,actions=['left_add','right_add','both_add','left_subtract','right_subtract','both_subtract','reset'],learningGoal='比较单侧变化与等式两边共同变化').model_dump()

def apply(spec,state,action):
    spec=VisualizationSpec.model_validate(spec)
    if action not in spec.actions:raise ValueError('不支持的操作')
    current=BalanceState.model_validate(state)
    if action=='reset':return spec.initial.model_dump()
    delta=spec.step*(-1 if action.endswith('subtract') else 1)
    result=current.model_dump()
    for side in ('left','right'):
        if action.startswith(side) or action.startswith('both'):result[side]+=delta
    if any(not spec.minimum<=v<=spec.maximum for v in result.values()):raise ValueError('操作超出数值边界')
    return result

def validate_progress(task,drafts):
    for block in task.snapshot.get('blocks',[]):
        value=(drafts.get('blocks') or {}).get(block.get('id'),{})
        if block.get('type')!='activity' or not value.get('visualization'):continue
        spec=specification(block.get('activity') or {})
        data=value['visualization']
        if not isinstance(data,dict) or set(data)-{'state','actions'}:raise ValueError('互动状态格式无效')
        actions=data.get('actions',[])
        if not isinstance(actions,list) or len(actions)>200:raise ValueError('互动动作最多200步，请重置后继续')
        state=spec['initial']
        for action in actions:state=apply(spec,state,action)
        if state!=data.get('state'):raise ValueError('互动状态与动作不一致')
        if value.get('completed') and (state['left']!=state['right'] or not actions or not str(value.get('explanation','')).strip()):raise ValueError('完成互动需平衡状态及自己的解释')
