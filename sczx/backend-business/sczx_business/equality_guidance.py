"""Small, explicit numeric examples; do not infer a student's hidden answer."""
import re
from .math_tools import compare_equivalence
from .model_provider import ModelError

def numeric_equality_example(prompt):
    text=prompt.replace('−','-').replace('（','(').replace('）',')')
    number=r'-?\d+(?:\.\d+)?'
    pair=re.search(r'(?<![A-Za-z0-9_+*/-])('+number+r')\s*=\s*('+number+r')(?![A-Za-z0-9_.])',text)
    operand=re.search(r'\b[a-zA-Z]\s*=\s*('+number+r')(?![A-Za-z0-9_.])',text)
    operation=re.search(r'两边[^。？！?\n]{0,18}?(减去|减|加上|加)',text)
    if not (pair and operand and operation):return None
    left,right=pair.groups();equal,verified=compare_equivalence(left,right)
    if not verified or not equal:return None
    sign='-' if operation.group(1).startswith('减') else '+'
    value=operand.group(1)
    return {'originalLeft':left,'originalRight':right,'operand':value,'operation':sign,'leftExpression':f'({left}){sign}({value})','rightExpression':f'({right}){sign}({value})'}

def validate_equality_explanation(result,example):
    if not example:return
    text='\n'.join([result.get('hint',''),*result.get('steps',[]),result.get('question','')]).replace('−','-').replace('（','(').replace('）',')')
    for left,right in re.findall(r'(?:把|将|让)\s*(-?\d+(?:\.\d+)?)\s*(?:和|与|、)\s*(-?\d+(?:\.\d+)?)\s*(?:都|同时|分别)',text):
        if not (compare_equivalence(left,example['originalLeft'])[0] and compare_equivalence(right,example['originalRight'])[0]):
            raise ModelError('把共同运算数混作了原等式的一边；请分别从原等式左右两边施加同一运算。')
    # A contrast can deliberately compare one changed side with an unchanged one.
    if re.search('只(?:变|改|对)|仅(?:变|改)|一边不变|对比|比较只',text):return
    question=result.get('question','').replace('−','-').replace('（','(').replace('）',')')
    for left,right in re.findall(r'([\d().+*/ -]+)\s*(?:和|与)\s*([\d().+*/ -]+)\s*分别(?:等于|得)',question):
        a=compare_equivalence(left.strip(),example['leftExpression']);b=compare_equivalence(right.strip(),example['rightExpression'])
        if a[1] and b[1] and a[0]!=b[0]:raise ModelError('追问只对等式一边施加了运算，与本轮两边共同运算不一致。')
