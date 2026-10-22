"""Prepare ONE explicitly disclosed due-date fixture for the dedicated demo account."""
from pathlib import Path
import json,os,subprocess,re
from dotenv import dotenv_values
R=Path(__file__).resolve().parents[3];B=R/'.runtime/competition-video/take2';proof=B/'review-fixture.json'
if proof.exists():
 print('Demo review fixture already prepared');raise SystemExit
account=json.loads((B/'account.json').read_text());state=json.loads((B/'demo-state.json').read_text())
assert re.fullmatch(r'xiaolin\.demo\.\d+@example\.com',account['email'])
assert re.fullmatch(r'[a-f0-9-]{36}',state['manualId'])
v=dotenv_values(R/'.env.cangjie');env=os.environ.copy();env['MYSQL_PWD']=v['CANGJIE_DB_PASSWORD']
args=['mysql','--protocol=TCP','-h',v.get('CANGJIE_DB_HOST','127.0.0.1'),'-P',v.get('CANGJIE_DB_PORT','3307'),'-u',v['CANGJIE_DB_USER'],'--database='+v['CANGJIE_DB_NAME'],'--batch','--raw','--skip-column-names']
def sql(q):
 p=subprocess.run(args,input=q,text=True,capture_output=True,env=env,check=True);return p.stdout.strip()
where=f"q.id='{state['manualId']}' AND u.email='{account['email']}' AND p.status='pending'"
query=f"SELECT p.id,p.due_at,p.interval_days FROM review_plans p JOIN questions q ON q.id=p.question_id JOIN users u ON u.id=p.user_id WHERE {where} ORDER BY p.created_at LIMIT 1;"
before=sql(query);assert before,'No naturally generated pending review plan for the demo question'
pid=before.split('\t')[0];assert re.fullmatch(r'[a-f0-9-]{36}',pid)
sql(f"UPDATE review_plans p JOIN questions q ON q.id=p.question_id JOIN users u ON u.id=p.user_id SET p.due_at=UTC_TIMESTAMP()-INTERVAL 30 SECOND,p.reason='演示账号预置到期任务；作答与再次调度实际运行' WHERE p.id='{pid}' AND {where};")
after=sql(query)
proof.write_text(json.dumps({'purpose':'展示到期复习；非真实跨日学习实验','scope':'仅独立演示账号的一条系统既有计划','question_id':state['manualId'],'plan_id':pid,'before':before,'after':after,'disclosure':'演示账号预置到期任务','changed_columns':['due_at','reason'],'grading_and_next_schedule':'由真实业务服务处理，未预置作答或判定'},ensure_ascii=False,indent=2))
print('Prepared exactly one disclosed review fixture:',pid)
