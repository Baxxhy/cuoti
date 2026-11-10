"""Bounded checks for known unsafe mathematical language; not a proof of prose."""
import re

def text_fields(value):
    if isinstance(value,str):return [value]
    if isinstance(value,list):return [t for v in value for t in text_fields(v)]
    if isinstance(value,dict):return [t for k,v in value.items() if k not in ('id','source','references','verification','mathClaims','reviewRecord','authorship') for t in text_fields(v)]
    return []

def inspect_conditions(value):
    issues=[]
    for text in text_fields(value):
        for clause in re.split(r'[。；;\n]',text):
            s=clause.strip()
            if not s:continue
            nonzero=bool(re.search(r'非零|不(?:等于|为)(?:零|0)|[≠]|!=\s*0|不能(?:是|为)(?:零|0)',s))
            # An explicit prohibition or discussion of an invalid operation is allowed.
            zero=re.search(r'(?:除以|同除以?|除数(?:是|为))\s*(?:零|0)(?![\d.])',s)
            if zero and not re.search(r'不能|不可以|禁止|不合法|未定义|错误|无法|不可',s):issues.append({'code':'division_by_zero','text':s,'message':'除数不能为零。'})
            generic=re.search(r'(?:同除以?|除以)(?:同(?:一|样)(?:个|的)?(?:数|量)|一个数|相同(?:的)?数|[a-zA-Z](?![a-zA-Z]))',s)
            # Covers the observed combined list: 加上、减去、乘上或除以同一个数.
            if generic and not nonzero and not re.search(r'不能|不可|条件不足|需(?:要)?核对|补充.*条件|没有.*条件',s):issues.append({'code':'division_condition_missing','text':s,'message':'涉及同除的规则必须明确非零条件。'})
            if re.search(r'(?:同乘|乘以|乘上)\s*(?:零|0)(?![\d.])',s):
                unsafe_loss=bool(re.search(r'不会.*丢失|不丢失',s))
                unsafe_reverse=bool(re.search(r'等价|可逆|恢复|唯一解',s)) and not re.search(r'不能|不可|丢失|不等价|不可逆',s)
                if unsafe_loss or unsafe_reverse:issues.append({'code':'zero_equivalence','text':s,'message':'同乘零不能作为保留原解的可逆变形。'})
    return {'status':'blocked' if issues else 'no_known_issue','issues':issues,'humanReviewRequired':True,'scope':'仅检测已知条件错误；未检出不代表全文数学正确'}

def require_conditions(value):
    from .model_provider import ModelError
    report=inspect_conditions(value)
    if report['issues']:raise ModelError('数学条件需修订，结果未采用：'+report['issues'][0]['message'])
    return report
