"""Real web proxy -> business HTTP -> algorithm HTTP -> isolated MySQL acceptance.

A known analysis is seeded as a fixture. OCR/model analysis and voice are not tested here.
"""
import json
import hashlib
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import httpx
import pymysql

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from sczx_api.database import Database
from sczx_api.schema import initialize_database
from sczx_api.security import new_id
from sczx_api.knowledge_seed import seed_public_knowledge
from browser_fixtures import seed_rendering,seed_personal_learning,seed_option_task,seed_task_entry,seed_function_entry,seed_experience,seed_inequality,seed_personas,seed_route_content


def port():
    with socket.socket() as listener:listener.bind(('127.0.0.1',0));return listener.getsockname()[1]


def main():
    artifacts=ROOT/'.runtime/http-smoke'/secrets.token_hex(4);artifacts.mkdir(parents=True)
    children=[];logs=[];report={'analysis':'seeded fixed fixture; no external model invocation','checks':[]}
    def spawn(name,args,cwd,env):
        log=(artifacts/(name+'.log')).open('wb');logs.append(log)
        child=subprocess.Popen(args,cwd=cwd,env=env,stdout=log,stderr=log);children.append(child);return child
    with tempfile.TemporaryDirectory(prefix='sczx-http-') as temporary:
        temp=Path(temporary);data=temp/'data';data.mkdir();mysql_socket=temp/'mysql.sock'
        env=os.environ.copy();env.update(SCZX_DB_NAME='sczx_http_smoke',SCZX_DB_USER='root',SCZX_DB_PASSWORD='',SCZX_DB_SOCKET=str(mysql_socket),SCZX_AUTH_SECRET=secrets.token_hex(32),SCZX_ALGORITHM_SECRET=secrets.token_hex(32),SCZX_MEDIA_ROOT=str(artifacts/'media'),SCZX_API_POOL_PATH=str(artifacts/'no-model-pool.json'),SCZX_AI_USE_ENV_PROXY='false',SCZX_TASK_WORKERS='2',LANGSMITH_TRACING='false')
        env.pop('PYTHONPATH',None)
        mysql=shutil.which('mysqld')
        if not mysql:raise SystemExit('需要本机 mysqld 才能运行隔离联调。')
        try:
            with (artifacts/'mysql-init.log').open('wb') as log:subprocess.run([mysql,'--no-defaults','--initialize-insecure','--user='+('root' if os.geteuid()==0 else os.environ.get('USER','')),'--datadir='+str(data),'--innodb-buffer-pool-size=32M','--innodb-log-file-size=16M'],stdout=log,stderr=log,check=True,timeout=60)
            spawn('mysql',[mysql,'--no-defaults','--user='+('root' if os.geteuid()==0 else os.environ.get('USER','')),'--datadir='+str(data),'--socket='+str(mysql_socket),'--pid-file='+str(temp/'mysql.pid'),'--skip-networking','--mysqlx=OFF','--innodb-buffer-pool-size=32M','--innodb-log-file-size=16M'],ROOT,env)
            deadline=time.monotonic()+40
            while True:
                try:connection=pymysql.connect(unix_socket=str(mysql_socket),user='root',autocommit=True);break
                except pymysql.MySQLError:
                    if time.monotonic()>deadline:raise RuntimeError('temporary MySQL failed to start') from None
                    time.sleep(.2)
            with connection:
                with connection.cursor() as cursor:cursor.execute('CREATE DATABASE sczx_http_smoke CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
            os.environ.update({k:v for k,v in env.items() if k.startswith('SCZX_')});initialize_database()
            if os.environ.get('SCZX_RUN_E2E')=='1':
                seed_public_knowledge()
                with Database.from_environment() as db:
                    before=db.query('SELECT code,id FROM knowledge_points ORDER BY code').rows
                    relations=db.query('SELECT source_id,target_id,relation_type FROM knowledge_relations ORDER BY source_id,target_id').rows
                seeded=subprocess.run([str(ROOT/'.venv/bin/python'),str(ROOT/'scripts/seed_knowledge.py')],cwd=ROOT,env=env,capture_output=True,text=True,timeout=30)
                (artifacts/'knowledge-seed.log').write_text(seeded.stdout+'\n'+seeded.stderr)
                assert seeded.returncode==0,seeded.stdout+'\n'+seeded.stderr
                with Database.from_environment() as db:
                    assert db.query('SELECT code,id FROM knowledge_points ORDER BY code').rows==before
                    assert db.query('SELECT source_id,target_id,relation_type FROM knowledge_relations ORDER BY source_id,target_id').rows==relations
                assert len(before)==250 and len(relations)==65
                report['checks'].append('public knowledge seed: 250 cards/65 relations; repeat preserves IDs and relations')
                with Database.from_environment() as db:
                    source=new_id()
                    db.query("INSERT INTO dataset_sources (id,`key`,name,version,homepage,license,local_path,total_items,imported_items,source_metadata,created_at,updated_at) VALUES (?,'sczx-browser-fixtures','浏览器验收样本','1','','fixture','',32,32,JSON_OBJECT(),UTC_TIMESTAMP(),UTC_TIMESTAMP())",[source])
                    for subject in ['数学','英语']:
                        for index in range(16):
                            stem=f'{subject}浏览器验收样本{index}: 1+1=?'
                            db.query("INSERT INTO dataset_questions (id,dataset_source_id,source_item_id,split,subject,grade,grade_band,title,question_text,question_type,options,answer,solution,knowledge_points,image_paths,difficulty,content_hash,source_metadata,has_answer,has_solution,answer_verified,quality_status,usable_for_practice,usable_for_auto_grade,created_at,updated_at) VALUES (?,?,?,'test',?,'高一','高中','浏览器验收题',?,'综合题',JSON_ARRAY(),JSON_QUOTE('2'),'验收样本',JSON_ARRAY('基础运算'),JSON_ARRAY(),'medium',?,JSON_OBJECT(),1,1,1,'ready',1,1,UTC_TIMESTAMP(),UTC_TIMESTAMP())",[new_id(),source,subject+str(index),subject,stem,hashlib.sha256(stem.encode()).hexdigest()])
                    study_source=new_id()
                    db.query("INSERT INTO dataset_sources (id,`key`,name,version,homepage,license,local_path,total_items,imported_items,source_metadata,created_at,updated_at) VALUES (?,'sczx-study-browser','练习验收题库','1','','fixture','',6,6,JSON_OBJECT(),UTC_TIMESTAMP(),UTC_TIMESTAMP())",[study_source])
                    for index in range(6):
                        stem=f'独立题库验收{index}: 1+1等于多少？'
                        db.query("INSERT INTO dataset_questions (id,dataset_source_id,source_item_id,split,subject,grade,grade_band,title,question_text,question_type,options,answer,solution,knowledge_points,image_paths,difficulty,content_hash,source_metadata,has_answer,has_solution,answer_verified,quality_status,usable_for_practice,usable_for_auto_grade,created_at,updated_at) VALUES (?,?,?,'test','数学','初一','初中','独立题库验收',?,'multiple-choice',JSON_ARRAY(JSON_OBJECT('key','A','text','2'),JSON_OBJECT('key','B','text','3')),JSON_QUOTE('A'),'1+1=2',JSON_ARRAY('基础运算'),JSON_ARRAY(),'medium',?,JSON_OBJECT(),1,1,1,'ready',1,1,UTC_TIMESTAMP(),UTC_TIMESTAMP())",[new_id(),study_source,str(index),stem,hashlib.sha256(stem.encode()).hexdigest()])
                    env.update(QA_STUDY_SOURCE=study_source,QA_STUDY_EMAIL='study-browser@example.test',QA_STUDY_PASSWORD='Study-browser-123')
                    env.update(seed_rendering(db,artifacts/'question-bank-images'))
                    os.environ['SCZX_QUESTION_BANK_ROOT']=env['SCZX_QUESTION_BANK_ROOT']
            if os.environ.get('SCZX_RUN_E2E')=='1':
                fixture_port=port()
                spawn('model-fixture',[str(ROOT/'.venv/bin/python'),str(ROOT/'scripts/model_fixture.py'),'--port',str(fixture_port),'--events',str(artifacts/'model-fixture-events.jsonl')],ROOT,env)
                deadline=time.monotonic()+10
                with httpx.Client(trust_env=False) as fixture_http:
                    while True:
                        try:
                            if fixture_http.get(f'http://127.0.0.1:{fixture_port}/livez').status_code==200:break
                        except httpx.TransportError:pass
                        if time.monotonic()>deadline:raise RuntimeError('controlled model fixture failed to start')
                        time.sleep(.1)
                    for rejected in ['unknown prompt','AnswerGradeOutput\n题目：3x+2=17\n标准答案：x=5\n学生作答：3x=18\nx=5\n请判断','AnswerGradeOutput\n题目：3x+2=17\n标准答案：x=5\n学生作答：3x=15\nx=5\n但x=9\n请判断']:
                        assert fixture_http.post(f'http://127.0.0.1:{fixture_port}/v1/chat/completions',json={'messages':[{'role':'user','content':rejected}]}).status_code==503
                report['checks'].append('controlled model rejects unknown and contradictory process prompts')
                pool=artifacts/'fixture-model-pool.json'
                pool.write_text(json.dumps([{'base_url':f'http://127.0.0.1:{fixture_port}/v1','api_key':'local-test-only','model':'Qwen'}]))
                env['SCZX_API_POOL_PATH']=str(pool)
                report['provider']='local controlled fixture; unknown prompts rejected; no external model calls'
            algorithm_port,backend_port,web_port=port(),port(),port()
            env.update(SCZX_ALGORITHM_URL=f'http://127.0.0.1:{algorithm_port}',SCZX_BACKEND_URL=f'http://127.0.0.1:{backend_port}')
            python=str(ROOT/'.venv/bin/python')
            env.update(SCZX_ALGORITHM_PORT=str(algorithm_port),SCZX_BACKEND_PORT=str(backend_port),SCZX_WEB_PORT=str(web_port))
            spawn('stack',[python,str(ROOT/'scripts/run_local.py')],ROOT,env)
            base=f'http://127.0.0.1:{web_port}'
            with httpx.Client(trust_env=False,timeout=45) as http:
                for url in [f'http://127.0.0.1:{algorithm_port}/livez',f'http://127.0.0.1:{backend_port}/readyz',base]:
                    deadline=time.monotonic()+30
                    while True:
                        try:
                            if http.get(url).status_code==200:break
                        except httpx.TransportError:pass
                        if time.monotonic()>deadline or any(c.poll() is not None for c in children):raise RuntimeError('service startup failed; inspect '+str(artifacts))
                        time.sleep(.2)
                def api(method,path,body=None,expected=200):
                    response=http.request(method,base+'/api/v1'+path,json=body,headers=headers)
                    assert response.status_code==expected,(path,response.status_code,response.text)
                    return response.json()['data']
                if os.environ.get('SCZX_RUN_E2E')=='1':
                    actor=http.post(base+'/api/v1/auth/register',json={'email':env['QA_STUDY_EMAIL'],'password':env['QA_STUDY_PASSWORD'],'grade':'初一'})
                    assert actor.status_code==200,actor.text
                    held=http.post(base+'/api/v1/study-sessions',headers={'Authorization':'Bearer '+actor.json()['data']['access_token']},json={'mode':'practice','question_ids':[env['QA_STUDY_BLOCKED_QUESTION']]})
                    assert held.status_code==200,held.text
                    env['QA_STUDY_BLOCKED_SESSION']=held.json()['data']['id']
                    with Database.from_environment() as db:db.query("UPDATE dataset_questions SET quality_status='format_review',usable_for_practice=0,usable_for_auto_grade=0 WHERE id=?",[env['QA_STUDY_BLOCKED_QUESTION']])
                    review_response=http.post(base+'/api/v1/auth/register',json={'email':'review-browser@example.test','password':'Review-browser-123','grade':'初一'})
                    assert review_response.status_code==200,review_response.text
                    reviewer=review_response.json()['data'];review_headers={'Authorization':'Bearer '+reviewer['access_token']};review_ids=[]
                    for index,stem in enumerate(['解方程 x+2=5','计算 7+5']):
                        created=http.post(base+'/api/v1/questions/manual',headers=review_headers,json={'question_text':stem,'subject':'数学','grade':'初一'})
                        assert created.status_code==200,created.text
                        plan_id=new_id();review_ids.append(plan_id)
                        with Database.from_environment() as db:db.query("INSERT INTO review_plans (id,user_id,question_id,due_at,interval_days,reason,status,created_at,updated_at) VALUES (?,?,?,UTC_TIMESTAMP()-INTERVAL ? DAY,1,'复习','pending',UTC_TIMESTAMP(),UTC_TIMESTAMP())",[plan_id,reviewer['id'],created.json()['data']['id'],2-index])
                    env.update(QA_REVIEW_QUEUE_TOKEN=reviewer['access_token'],QA_REVIEW_QUEUE_FIRST=review_ids[0],QA_REVIEW_QUEUE_SECOND=review_ids[1])
                    route_email,route_password='route-browser@example.test','Route-browser-123'
                    routed=http.post(base+'/api/v1/auth/register',json={'email':route_email,'password':route_password,'grade':'初一'})
                    assert routed.status_code==200,routed.text
                    route_actor=routed.json()['data']
                    routed_question=http.post(base+'/api/v1/questions/manual',headers={'Authorization':'Bearer '+route_actor['access_token']},json={'question_text':'解方程：2x+3=11','student_answer':'x=7','student_steps':['2x=11+3','x=7'],'subject':'数学','grade':'初一'})
                    assert routed_question.status_code==200,routed_question.text
                    route_qid=routed_question.json()['data']['id']
                    with Database.from_environment() as db:
                        point=db.query("SELECT id FROM knowledge_points WHERE code='math.equation_property'").rows[0]['id']
                        db.query("INSERT INTO user_question_knowledge_links (id,user_id,question_id,knowledge_point_id,`role`,confidence,mapping_method,evidence_text,created_at,updated_at) VALUES (?,?,?,?,'primary',1,'fixture','受控图谱布局验收',UTC_TIMESTAMP(),UTC_TIMESTAMP())",[new_id(),route_actor['id'],route_qid,point])
                    seed_route_content(route_qid,env)
                    env.update(QA_ROUTE_EMAIL=route_email,QA_ROUTE_PASSWORD=route_password,QA_ROUTE_QUESTION=route_qid,QA_ROUTE_QUESTION_ID=route_qid)
                    admin_email,admin_password='admin-browser@example.test','Admin-browser-123'
                    admin=http.post(base+'/api/v1/auth/register',json={'email':admin_email,'password':admin_password,'name':'隔离管理员'})
                    assert admin.status_code==200,admin.text
                    with Database.from_environment() as db:
                        db.query("UPDATE users SET role='admin' WHERE id=?",[admin.json()['data']['id']])
                        db.query("INSERT INTO tutor_sessions (id,user_id,question_id,stage,hint_level,turn_count,mastery_score,state,status,created_at,updated_at) VALUES (?,?,?,'understanding',0,0,0,JSON_OBJECT(),'active',UTC_TIMESTAMP(),UTC_TIMESTAMP())",[new_id(),route_actor['id'],route_qid])
                    env.update(QA_ROLE_TESTS='1',QA_ADMIN_EMAIL=admin_email,QA_ADMIN_PASSWORD=admin_password)
                    person=http.post(base+'/api/v1/auth/register',json={'email':'personal-browser@example.test','password':'Personal-browser-123','grade':'初一'})
                    assert person.status_code==200,person.text
                    personal_actor=person.json()['data'];personal_headers={'Authorization':'Bearer '+personal_actor['access_token']};personal_questions=[]
                    for index in range(22):
                        created=http.post(base+'/api/v1/questions/manual',headers=personal_headers,json={'question_text':f'长期检索{index}：2x+1=2','subject':'数学','grade':'初一'})
                        assert created.status_code==200,created.text
                        personal_questions.append(created.json()['data']['id'])
                    with Database.from_environment() as db:env.update(seed_personal_learning(db,personal_actor['id'],personal_questions))
                    env['QA_PERSONAL_TOKEN']=personal_actor['access_token']
                    recovery=http.post(base+'/api/v1/auth/register',json={'email':'review-recovery@example.test','password':'Review-recovery-123','grade':'初一'})
                    assert recovery.status_code==200,recovery.text
                    recovery_actor=recovery.json()['data'];recovery_headers={'Authorization':'Bearer '+recovery_actor['access_token']}
                    recovery_question=http.post(base+'/api/v1/questions/manual',headers=recovery_headers,json={'question_text':'解方程 3x+2=17','subject':'数学','grade':'初一'})
                    assert recovery_question.status_code==200,recovery_question.text
                    recovery_qid=recovery_question.json()['data']['id'];recovery_plan=new_id();recovery_analysis=new_id()
                    with Database.from_environment() as db:
                        db.query("INSERT INTO problem_analyses (id,question_id,subject,problem_type,known_conditions,goal,knowledge_points,prerequisites,final_answer,verified,raw_result,created_at,updated_at) VALUES (?,?,'数学','方程',JSON_ARRAY(),'求x',JSON_ARRAY('等式的性质'),JSON_ARRAY(),'x=5',1,JSON_OBJECT('fixture',true),UTC_TIMESTAMP(),UTC_TIMESTAMP())",[recovery_analysis,recovery_qid])
                        for index,text in enumerate(['3x=15','x=5']):db.query("INSERT INTO reference_steps (id,analysis_id,step_index,text,explanation,math_valid,uses_condition,created_at,updated_at) VALUES (?,?,?,?, '',1,0,UTC_TIMESTAMP(),UTC_TIMESTAMP())",[new_id(),recovery_analysis,index,text])
                        db.query("INSERT INTO review_plans (id,user_id,question_id,due_at,interval_days,reason,status,created_at,updated_at) VALUES (?,?,?,UTC_TIMESTAMP()-INTERVAL 1 DAY,1,'复习','pending',UTC_TIMESTAMP(),UTC_TIMESTAMP())",[recovery_plan,recovery_actor['id'],recovery_qid])
                    env.update(QA_REVIEW_TOKEN=recovery_actor['access_token'],QA_REVIEW_PLAN_ID=recovery_plan)
                response=http.post(base+'/api/v1/auth/register',json={'email':'http-smoke@example.com','password':'local-test-password'})
                assert response.status_code==200,response.text
                user=response.json()['data'];headers={'Authorization':'Bearer '+user['access_token']}
                question=api('POST','/questions/manual',{'question_text':'解方程：2x+3=11','grade':'初一','student_steps':['2x=11+3','x=7'],'knowledge_points':['等式的性质']})
                qid=question['id'];analysis_id=new_id()
                with Database.from_environment() as db:
                    db.query("INSERT INTO problem_analyses (id,question_id,subject,problem_type,known_conditions,goal,knowledge_points,prerequisites,final_answer,verified,raw_result,created_at,updated_at) VALUES (?,?,'数学','方程',JSON_ARRAY(),'求x',JSON_ARRAY('等式的性质'),JSON_ARRAY(),'x=4',1,JSON_OBJECT('fixture',true),UTC_TIMESTAMP(),UTC_TIMESTAMP())",[analysis_id,qid])
                    for index,text in enumerate(['2x=8','x=4']):db.query("INSERT INTO reference_steps (id,analysis_id,step_index,text,explanation,math_valid,uses_condition,created_at,updated_at) VALUES (?,?,?,?, '',1,0,UTC_TIMESTAMP(),UTC_TIMESTAMP())",[new_id(),analysis_id,index,text])
                task=api('POST','/learning-tasks',{'question_id':qid,'request_id':'http-task'},202)
                result=subprocess.run(['node',str(ROOT/'scripts/browser_live.mjs')],input=json.dumps({'base':base,'token':user['access_token'],'task_id':task['id'],'question_id':qid,'artifacts':str(artifacts)}),text=True,cwd=ROOT,env=env,capture_output=True,timeout=100)
                assert result.returncode==0,result.stdout+'\n'+result.stderr
                report['checks'].append('browser task workflow and refresh')
                print(result.stdout.strip(),flush=True)
                paper=api('POST','/papers',{'title':'真实联调试卷','question_ids':[qid]})
                for kind,signature in [('question',b'%PDF-'),('answer',b'%PDF-'),('excel',b'PK')]:
                    job=api('POST','/papers/'+paper['id']+'/export',{'kind':kind})
                    downloaded=http.get(base+job['url'])
                    assert downloaded.status_code==200 and downloaded.content.startswith(signature)
                    assert http.get(base+'/api/v1/papers/'+paper['id']+'/download?kind='+kind,headers=headers).content==downloaded.content
                    (artifacts/('paper-'+kind+('.xlsx' if kind=='excel' else '.pdf'))).write_bytes(downloaded.content)
                report['checks'].append('real algorithm HTTP PDF/answer/Excel export and download')
                compatibility=subprocess.run(['node',str(ROOT/'scripts/browser_smoke.mjs')],cwd=ROOT,env={**env,'SCZX_WEB_URL':base},capture_output=True,text=True,timeout=45)
                assert compatibility.returncode==0,compatibility.stdout+'\n'+compatibility.stderr
                report['checks'].append('controlled login/register/image-picker browser compatibility')
                if os.environ.get('SCZX_RUN_E2E')=='1':
                    env['QA_OPTIONS_FIXTURE']=seed_option_task(http,base,artifacts,env)
                    env.update(seed_function_entry(http,base))
                    env.update(seed_experience(http,base))
                    env.update(seed_inequality(http,base))
                    env.update(seed_personas(http,base))
                    clear_entry=seed_task_entry(http,base)
                    env.update(clear_entry)
                    env.update(QA_TASK_EMAIL='clear-entry-browser@example.test',QA_TASK_PASSWORD='Clear-entry-browser-123',QA_TASK_QUESTION_ID=clear_entry['QA_ENTRY_CLEAR_QUESTION_ID'])
                    env.update(seed_task_entry(http,base,wrong=True))
                    draft_entry=seed_task_entry(http,base,wrong=True,identity='draft-entry')
                    env.update(QA_DRAFT_EMAIL='draft-entry-browser@example.test',QA_DRAFT_PASSWORD='Clear-entry-browser-123',QA_DRAFT_QUESTION_ID=draft_entry['QA_ENTRY_QUESTION_ID'])
                    budget_entry=seed_task_entry(http,base,wrong=True,identity='budget-entry')
                    with Database.from_environment() as db:db.query("UPDATE learning_tasks SET checkpoint=JSON_SET(checkpoint,'$.rounds',24) WHERE id=?",[budget_entry['QA_ENTRY_TASK_ID']])
                    env.update(QA_BUDGET_EMAIL='budget-entry-browser@example.test',QA_BUDGET_PASSWORD='Clear-entry-browser-123',QA_BUDGET_QUESTION_ID=budget_entry['QA_ENTRY_QUESTION_ID'],QA_BUDGET_TASK_ID=budget_entry['QA_ENTRY_TASK_ID'])
                    acceptance_args=['node',str(ROOT/'frontend/node_modules/@playwright/test/cli.js'),'test','--config',str(ROOT/'frontend/playwright.config.js')]
                    if os.environ.get('SCZX_E2E_GREP'):acceptance_args.extend(['--grep',os.environ['SCZX_E2E_GREP']])
                    report['e2e_scope']=os.environ.get('SCZX_E2E_GREP','all migrated cases')
                    acceptance=subprocess.run(acceptance_args,cwd=ROOT,env={**env,'SCZX_WEB_URL':base,'SCZX_API_URL':base+'/api/v1','SCZX_E2E_OUTPUT':str(artifacts/'e2e')},capture_output=True,text=True,timeout=600)
                    (artifacts/'e2e.log').write_text(acceptance.stdout+'\n'+acceptance.stderr)
                    assert acceptance.returncode==0,acceptance.stdout+'\n'+acceptance.stderr
                    report['checks'].append('migrated browser acceptance on Python/MySQL')
                    events=artifacts/'model-fixture-events.jsonl'
                    report['controlled_grades']=len(events.read_text().splitlines()) if events.exists() else 0
                    if not os.environ.get('SCZX_E2E_GREP') or '到期复习' in os.environ['SCZX_E2E_GREP']:assert report['controlled_grades']>=1
                with Database.from_environment() as db:
                    assert db.query('SELECT evidence_count FROM mastery_states WHERE user_id=?',[user['id']]).rows[0]['evidence_count']=='2'
                report['checks'].append('two objective learning observations persisted')
            report['success']=True;(artifacts/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
            print('PASS: independent web/business/algorithm HTTP stack; report '+str(artifacts/'report.json'),flush=True)
        finally:
            for child in reversed(children):
                if child.poll() is None:child.terminate()
            for child in reversed(children):
                try:child.wait(timeout=12)
                except subprocess.TimeoutExpired:child.kill();child.wait()
            for log in logs:log.close()


if __name__=='__main__':main()
