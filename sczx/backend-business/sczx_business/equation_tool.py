"""Server-replayed reversible transformations. Only data, never executable model code."""
import copy
import sympy as sp
from fastapi import APIRouter,Depends,Request,HTTPException
from sqlalchemy import select
from .database import get_db
from .models import StudentRecord,LearningTask
from .exam_models import EquationProgress
from .teaching import user_for,accessible_task,ensure_write
from .math_tools import parse_math_expression,solve_text_equation
router=APIRouter(prefix='/api/equation-tools')
def replay(equation,actions):
 if not solve_text_equation(equation)[1]:raise ValueError('仅支持可核对的单变量单解方程。')
 lhs,rhs=map(parse_math_expression,equation.split('='));steps=[]
 for action in actions:
  op=action.get('operation');value=action.get('value')
  if op not in ('add','subtract','multiply','divide') or not isinstance(value,str) or len(value)>20:raise ValueError('操作格式无效。')
  n=parse_math_expression(value)
  if n.free_symbols or not n.is_Rational or abs(n)>1000 or n.q>1000:raise ValueError('请输入范围内的有理数。')
  if op in ('multiply','divide') and n==0:raise ValueError('可逆变形的乘数、除数必须非零；乘零会丢失信息。')
  def apply(x):return sp.expand(x+n if op=='add' else x-n if op=='subtract' else x*n if op=='multiply' else x/n)
  lhs,rhs=apply(lhs),apply(rhs);steps.append({'equation':str(lhs)+' = '+str(rhs),'basis':'两边共同'+{'add':'加','subtract':'减','multiply':'乘','divide':'除以'}[op]+str(n)+('（非零）' if op in ('multiply','divide') else '')})
 return {'type':'equation-transform','initial':equation,'equation':str(lhs)+' = '+str(rhs),'steps':steps,'allowedOperations':['add','subtract','multiply','divide','undo','reset']}
def access(db,request,rid,index,write=False):
 u=user_for(request,db);r=db.get(StudentRecord,rid)
 if not r:raise HTTPException(404,'学习记录不存在。')
 t=accessible_task(db,u,r.task_id)
 if u.role=='student' and r.student_id!=u.id:raise HTTPException(404,'学习记录不存在。')
 if write:ensure_write(db,u,t.id)
 if not 0<=index<len(t.questions):raise HTTPException(422,'题目不存在。')
 return r,t.questions[index].get('equation','')
def value(row,equation):return {'revision':row.revision if row else 0,'actions':row.actions if row else [],'explanation':row.explanation if row else '','visualization':replay(equation,row.actions if row else [])}
@router.get('/{record_id}/{index}')
def get(record_id:str,index:int,request:Request,db=Depends(get_db)):
 r,e=access(db,request,record_id,index);row=db.scalar(select(EquationProgress).where(EquationProgress.record_id==r.id,EquationProgress.question==index))
 try:return value(row,e)
 except ValueError as error:raise HTTPException(422,str(error)) from None
@router.put('/{record_id}/{index}')
def put(record_id:str,index:int,body:dict,request:Request,db=Depends(get_db)):
 r,e=access(db,request,record_id,index,True);row=db.scalar(select(EquationProgress).where(EquationProgress.record_id==r.id,EquationProgress.question==index).with_for_update());revision=row.revision if row else 0
 if body.get('revision')!=revision:raise HTTPException(409,'操作已更新，请重新读取。')
 actions=copy.deepcopy(body.get('actions'));explanation=body.get('explanation','')
 if not isinstance(actions,list) or len(actions)>60 or not isinstance(explanation,str) or len(explanation)>6000:raise HTTPException(422,'操作最多60步，解释最多6000字。')
 try:replay(e,actions)
 except (ValueError,AttributeError,TypeError) as error:raise HTTPException(422,str(error)) from None
 if not row:row=EquationProgress(id='eq-'+r.id[7:35]+'-'+str(index),record_id=r.id,question=index,revision=0);db.add(row)
 row.actions=actions;row.explanation=explanation;row.revision=revision+1;db.commit();return value(row,e)
