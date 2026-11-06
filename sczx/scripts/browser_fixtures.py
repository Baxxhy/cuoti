"""Isolated rendering fixtures matching the original study smoke samples."""
import hashlib
import json
from PIL import Image,ImageDraw
from sczx_api.security import new_id


def insert(db,table,values):
    columns=list(values)
    db.query('INSERT INTO `'+table+'` ('+','.join('`'+key+'`' for key in columns)+',created_at,updated_at) VALUES ('+','.join('?' for _ in columns)+',UTC_TIMESTAMP(),UTC_TIMESTAMP())',[json.dumps(value,ensure_ascii=False) if isinstance(value,(list,dict)) else value for value in values.values()])


def source(db,key,name):
    value=new_id()
    insert(db,'dataset_sources',dict(id=value,key=key,name=name,version='1',homepage='',license='fixture',local_path='',total_items=1,imported_items=1,source_metadata={}))
    return value


def question(db,source_id,stem,options,answer,solution,**extra):
    value=dict(id=new_id(),dataset_source_id=source_id,source_item_id='rendering',split='test',subject='数学',grade='初一',grade_band='初中',title='呈现验收样本',question_text=stem,question_type='multiple-choice',options=options,answer=json.dumps(answer),solution=solution,knowledge_points=['基础运算'],image_paths=[],difficulty='medium',content_hash=hashlib.sha256(stem.encode()).hexdigest(),source_metadata={},has_answer=1,has_solution=1,answer_verified=1,quality_status='ready',usable_for_practice=1,usable_for_auto_grade=1)
    value.update(extra);insert(db,'dataset_questions',value)
    return value['id']


def seed_rendering(db,root):
    root.mkdir(parents=True,exist_ok=True)
    paths=[]
    for index,label in enumerate(['QUESTION','OPTION A','SOLUTION 1','SOLUTION 2']):
        path=root/f'figure-{index}.png'
        image=Image.new('RGB',(320,180),'white');draw=ImageDraw.Draw(image)
        draw.rectangle((25,25,295,155),outline='#3157a8',width=3);draw.text((50,70),label,fill='#3157a8')
        image.save(path);paths.append(str(path))
    figures=source(db,'sczx-figure-rendering','图片排版验收')
    question(db,figures,'如图，计算 $1+1$。<ImageHere>选择正确的选项图。',[{'key':'A','text':'<ImageHere>'},{'key':'B','text':'3'}],'A','第一步<ImageHere>第二步<ImageHere>',image_paths=paths,source_metadata={'has_visual':True})
    chemical=source(db,'sczx-chemical-rendering','化学排版验收题库')
    question(db,chemical,r'胆矾\mathrm{CuSO_{4}5H_{2}O}可写作$${[Cu(H_{2}O)_{4}]SO_{4}H_{2}O}$$，下列说法正确的是',[
        {'key':'A','text':r'所有氧原子都采取$${sp^{3}}$$杂化'},
        {'key':'B','text':'氧原子存在配位键和氢键两种化学键'},
        {'key':'C','text':r'$${Cu^{2+}}$$的价电子排布式为$${3d^{8}4s^{1}}$$'},
        {'key':'D','text':'胆矾中的水在不同温度下会分步失去'}
    ],'D',r'水分步失去。独立公式：\[Cu^{2+}\]',subject='化学',grade='高二',grade_band='高中')
    blocked=source(db,'sczx-blocked-rendering','停用题验收')
    blocked_id=question(db,blocked,r'不应展示的坏公式 $$\overset{⇌}$$',[{'key':'A','text':'甲'},{'key':'B','text':'乙'}],'A','验收样本')
    return {'QA_STUDY_FIGURE_SOURCE':figures,'QA_STUDY_CHEM_SOURCE':chemical,'SCZX_QUESTION_BANK_ROOT':str(root),'QA_STUDY_BLOCKED_QUESTION':blocked_id}
