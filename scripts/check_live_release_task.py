"""Bounded actual student task, solving only public question blocks, no hidden answers."""
import json
import os
import time
from argparse import ArgumentParser
from pathlib import Path
from uuid import uuid4

import httpx
from app.services.math_tools import solve_text_equation


def main(verify_existing=False):
    root = Path(__file__).resolve().parents[1]
    os.umask(0o077)
    actor = next(row for row in json.loads((root/'.runtime/student-personas-accounts.json').read_text()) if row['name']=='乙')
    report = {'kind':'actual-pool-full-linear-task', 'student_trial':False, 'steps':[], 'passed':False}
    path = root/'.runtime/release-live-task.json'

    def save():
        if verify_existing:
            return
        path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        path.chmod(0o600)

    with httpx.Client(base_url='http://127.0.0.1:8002/api/v1',timeout=180) as client:
        token = ''

        def request(method, url, payload=None):
            if verify_existing and method != 'GET' and not (method == 'POST' and url == '/auth/login'):
                raise RuntimeError('只读复核不会创建任务或提交作答')
            response=client.request(method,url,json=payload,headers={'Authorization':'Bearer '+token} if token else {})
            if response.status_code not in (200,202):
                raise RuntimeError('本机业务请求未成功，HTTP '+str(response.status_code))
            return response.json()['data']

        def wait(task_id):
            end=time.monotonic()+70
            while time.monotonic()<end:
                current=request('GET','/learning-tasks/'+task_id)
                if current['status'] not in ('queued','running'): return current
                time.sleep(.3)
            raise RuntimeError('实际任务等待超过限定窗口')

        token=request('POST','/auth/login',{'email':actor['email'],'password':actor['password']})['access_token']
        if verify_existing:
            report=json.loads(path.read_text())
            task=request('GET','/learning-tasks/'+report['task_id'])
            assert task['question_id']==actor['question_id']
            if task['status'] != 'completed':
                raise RuntimeError('只读复核要求任务已完成，不会继续提交作答')
        else:
            task=request('POST','/learning-tasks',{'question_id':actor['question_id'],'request_id':str(uuid4())})
            report['task_id']=task['id']
        report['question_id']=actor['question_id']
        save()
        task=wait(task['id'])
        for _ in range(4):
            if task['status']=='completed': break
            assert task['status']=='waiting_student'
            title=task['student_view']['title']
            if title=='先订正这一步':
                answer='2x=8'
            elif title=='独立完成这道题':
                answer='x=4'
            elif title=='换个条件，再试一次':
                question=next(block['text'] for block in task['student_view']['prompt_blocks'] if block['kind']=='question')
                answer,verified=solve_text_equation(question.replace('$',''))
                assert verified, '不能可靠求解公开对照题，停止而不读取隐藏答案'
            else:
                raise RuntimeError('遇到核验脚本尚未覆盖的任务类型')
            request('POST','/learning-tasks/'+task['id']+'/actions',{
                'kind':'answer','text':answer,'version':task['version'],
                'step_id':task['step_id'],'input_fingerprint':task['input_fingerprint'],
                'request_id':str(uuid4()),
            })
            report['steps'].append({'title':title,'answer':answer})
            save()
            task=wait(task['id'])
        assert task['status']=='completed' and len(report['steps'])==3
        history=request('GET','/learning-tasks/'+task['id']+'/history')
        correct={row.get('phase') for row in history['items'] if row.get('verdict')=='confirmed_correct'}
        assert {'repair','independent','contrast'}.issubset(correct)
        journey=request('GET','/questions/'+actor['question_id']+'/journey')
        assert journey['learning_tasks']['repair_verified']
        assert journey['learning_tasks']['original_independent']
        assert journey['learning_tasks']['near_transfer']
        assert not next(row for row in journey['stages'] if row['key']=='transfer')['completed']
        report.update(passed=True,status=task['status'],history_phases=sorted(correct),
                      original_preserved=request('GET','/questions/'+actor['question_id'])['student_answer']=='x=7',
                      single_contrast_not_full_mastery=True)
        assert report['original_preserved']
        save()
        print(json.dumps(report,ensure_ascii=False),flush=True)


if __name__=='__main__':
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--verify-existing', action='store_true', help='只读核对上次已完成任务，不重复作答')
    args = parser.parse_args()
    try:
        main(verify_existing=args.verify_existing)
    except (OSError,ValueError,KeyError,AssertionError,RuntimeError,httpx.HTTPError):
        print('实际学习闭环未通过，已完成阶段仅见本机私有报告；不输出凭据或上游响应',flush=True)
        raise SystemExit(1) from None
