from typing import Literal
from pydantic import BaseModel,Field,ConfigDict
from .ai_schemas import ChoiceOption,ResponseType,GradingMode
class BankInput(BaseModel):
 model_config=ConfigDict(extra='forbid')
 prompt:str=Field(min_length=1,max_length=6000)
 equation:str=Field(default='',max_length=500)
 answer:str=Field(min_length=1,max_length=1000)
 explanation:str=Field(min_length=1,max_length=6000)
 subject:str=Field(default='',min_length=1,max_length=80)
 grade:str=Field(default='',min_length=1,max_length=80)
 knowledgeIds:list[str]=Field(min_length=1,max_length=16)
 unitId:str=Field(default='',max_length=40)
 kind:Literal['calculation','application','explanation','single_choice','multiple_choice','true_false','fill_blank','short_answer','essay','proof','reading','writing','translation','experiment','programming']='calculation'
 difficulty:Literal['easy','medium','hard']='easy'
 points:int=Field(default=10,ge=1,le=100)
 source:str=Field(min_length=1,max_length=2000)
 responseType:str=''
 gradingMode:str=''
 options:list[dict]=Field(default_factory=list,max_length=12)
 rubric:str=Field(default='',max_length=6000)
 hint:str=Field(default='',max_length=6000)
 acceptedAnswers:list[str]=Field(default_factory=list,max_length=20)
 caseSensitive:bool=True
 requiresTeacherReview:bool=False
class ExamCandidate(BaseModel):
 responseType:ResponseType='short_answer'
 gradingMode:GradingMode='manual'
 options:list[ChoiceOption]=Field(default_factory=list,max_length=12)
 rubric:str=''
 model_config=ConfigDict(extra='forbid')
 prompt:str=Field(min_length=1,max_length=6000)
 equation:str=Field(default='',max_length=500)
 answer:str=Field(min_length=1,max_length=1000)
 explanation:str=Field(min_length=1,max_length=6000)
