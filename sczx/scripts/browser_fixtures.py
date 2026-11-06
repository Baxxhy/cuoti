"""Isolated rendering fixtures matching the original study smoke samples."""
import hashlib
import json
from pathlib import Path
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


def seed_personal_learning(db,owner,question_ids):
    """Persist the original personal-learning browser fixture, without model output."""
    code='personal.browser';card_id=new_id()
    insert(db,'knowledge_points',dict(id=card_id,code=code,subject='数学',name='长期学习等式性质',content={'grade':'初一','chapter':'长期学习验收章节','definition':'等式两边同时加上或减去同一个数，等式仍成立。','formulas':[r'a=b \Rightarrow a+c=b+c']}))
    first_plan=None
    for index,qid in enumerate(question_ids):
        db.query('UPDATE questions SET knowledge_points=? WHERE id=?',[json.dumps(['长期学习等式性质'],ensure_ascii=False),qid])
        plan=new_id()
        insert(db,'review_plans',dict(id=plan,user_id=owner,question_id=qid,interval_days=1,due_at='2099-01-01 00:00:00' if index==21 else '2020-01-01 00:00:00',reason='移项符号待巩固',status='pending'))
        if index==0:
            first_plan=plan
            insert(db,'user_question_knowledge_links',dict(id=new_id(),user_id=owner,question_id=qid,knowledge_point_id=card_id,role='primary',confidence=1,mapping_method='fixture',evidence_text='受控验收'))
    insert(db,'mastery_states',dict(id=new_id(),user_id=owner,subject='数学',knowledge_point='长期学习等式性质',mastery_score=.4,confidence=.8,evidence_count=2,near_transfer_rate=0,far_transfer_rate=0,forgetting_risk=0,update_reason='受控验收'))
    result={'explanation':'受控历史讲解','key_points':['两边同时运算'],'check_question':'为什么要同时运算？','sources':[{'name':'等式的性质'}]}
    db.query('INSERT INTO knowledge_lessons (id,user_id,knowledge_code,request_id,input_fingerprint,prompt,result,created_at) VALUES (?,?,?,?,?,?,?,UTC_TIMESTAMP(6))',[new_id(),owner,code,'fixture-history','old','历史提问',json.dumps(result,ensure_ascii=False)])
    return {'QA_PERSONAL_QUESTION':question_ids[0],'QA_PERSONAL_PLAN':first_plan,'QA_PERSONAL_CODE':code}


def seed_option_task(http,base,artifacts,env):
    """Create a real task then remove its option projection to test legacy hydration."""
    import time
    from sczx_api.database import Database
    registered=http.post(base+'/api/v1/auth/register',json={'email':'options-browser@example.test','password':'Options-browser-123','grade':'高一'})
    assert registered.status_code==200,registered.text
    actor=registered.json()['data'];headers={'Authorization':'Bearer '+actor['access_token']}
    choices=[{'label':label,'text':text} for label,text in zip('ABCD',[r'$\{x|-2\le x<1\}$',r'$\{x|-2<x\le1\}$',r'$\{x|x\ge-2\}$',r'\{x|x<1\}'])]
    created=http.post(base+'/api/v1/questions/manual',headers=headers,json={'question_text':r'已知集合 $M=\{x|x+2\ge0\},N=\{x|x-1<0\}$，则 $M\cap N=$（ ）','subject':'数学','grade':'高一','question_type':'单选题','options':choices,'student_answer':'D'})
    assert created.status_code==200,created.text
    qid=created.json()['data']['id'];path='uploads/options-browser-figure.png';image_file=Path(env['SCZX_MEDIA_ROOT'])/path
    image_file.parent.mkdir(parents=True,exist_ok=True)
    image=Image.new('RGB',(320,90),'white');draw=ImageDraw.Draw(image);draw.line((20,45,300,45),fill='black',width=2);draw.line((75,45,235,45),fill='#426dcc',width=4);draw.ellipse((70,40,80,50),fill='#426dcc');draw.ellipse((230,40,240,50),fill='white',outline='#426dcc',width=2);draw.text((70,62),'-2',fill='black');draw.text((232,62),'1',fill='black');image.save(image_file)
    with Database.from_environment() as db:
        insert(db,'problem_analyses',dict(id=new_id(),question_id=qid,subject='数学',problem_type='集合',known_conditions=[],goal='选择交集',knowledge_points=[],prerequisites=[],final_answer='A',verified=1,raw_result={'fixture':True}))
        insert(db,'question_assets',dict(id=new_id(),question_id=qid,kind='question_figure',path=path,sha256=hashlib.sha256(image_file.read_bytes()).hexdigest(),bbox=[]))
    response=http.post(base+'/api/v1/learning-tasks',headers=headers,json={'question_id':qid,'request_id':'options-browser'})
    assert response.status_code==202,response.text
    task=response.json()['data'];deadline=time.monotonic()+55
    while task['status'] in ['queued','running']:
        assert time.monotonic()<deadline,task
        time.sleep(.2)
        response=http.get(base+'/api/v1/learning-tasks/'+task['id'],headers=headers)
        assert response.status_code==200,response.text
        task=response.json()['data']
    assert task['status']=='waiting_student',task
    with Database.from_environment() as db:db.query("UPDATE learning_tasks SET student_view=JSON_REMOVE(student_view,'$.prompt_blocks[0].options') WHERE id=?",[task['id']])
    fixture=artifacts/'options-browser.json';fixture.write_text(json.dumps({'token':actor['access_token'],'question_id':qid,'task_id':task['id'],'figure':True}))
    return str(fixture)
