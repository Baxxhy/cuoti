from typing import Literal
from pydantic import BaseModel,Field,ConfigDict
class BankInput(BaseModel):
 model_config=ConfigDict(extra='forbid')
 prompt:str=Field(min_length=1,max_length=6000)
 equation:str=Field(default='',max_length=500)
 answer:str=Field(min_length=1,max_length=1000)
 explanation:str=Field(min_length=1,max_length=6000)
 subject:str=Field(default='数学',min_length=1,max_length=80)
 grade:str=Field(default='七年级',min_length=1,max_length=80)
 knowledgeIds:list[str]=Field(min_length=1,max_length=16)
 unitId:str=Field(default='unit-equation',max_length=40)
 kind:Literal['calculation','application','explanation']='calculation'
 difficulty:Literal['easy','medium','hard']='easy'
 points:int=Field(default=10,ge=1,le=100)
 source:str=Field(min_length=1,max_length=2000)
 requiresTeacherReview:bool=False
class ExamCandidate(BaseModel):
 model_config=ConfigDict(extra='forbid')
 prompt:str=Field(min_length=1,max_length=6000)
 equation:str=Field(min_length=1,max_length=500)
 answer:str=Field(min_length=1,max_length=1000)
 explanation:str=Field(min_length=1,max_length=6000)
