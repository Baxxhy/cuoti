"""Three bounded public equation samples through the actual pool, not a student study.

Creates separate QA students; stores credentials only in an ignored 0600 runtime file.
No pool credentials or upstream error bodies are printed.
"""
import json
import os
import time
from pathlib import Path
from uuid import uuid4

import httpx


def main():
    root = Path(__file__).resolve().parents[1]
    output = root / '.runtime/student-personas-live.json'
    accounts = root / '.runtime/student-personas-accounts.json'
    os.umask(0o077)
    output.parent.mkdir(exist_ok=True)
    results, credentials = [], []
    samples = [
        ('甲', '3x+2=17', ['3x=17+2', 'x=19/3'], 'x=19/3', '5', 0),
        ('乙', '2x+3=11', ['2x=11+3', 'x=7'], 'x=7', '4', 0),
        ('丙', '3x+2=17', ['3x=17-2', '3x=15', 'x=5'], 'x=5', '5', None),
    ]
    base = 'http://127.0.0.1:8002/api/v1'
    with httpx.Client(timeout=180) as client:
        def request(method, path, body=None, token=None):
            response = client.request(method, base + path, json=body,
                                      headers={'Authorization': 'Bearer '+token} if token else {})
            if response.status_code not in (200, 202):
                raise RuntimeError('本机业务HTTP '+str(response.status_code))
            return response.json()['data']

        for name, equation, steps, answer, expected, first in samples:
            row = {'student': name, 'equation': equation, 'expected_first_error': first}
            results.append(row)
            started = time.monotonic()
            try:
                account = {'email': f'persona-{uuid4().hex}@example.test', 'password': uuid4().hex}
                user = request('POST', '/auth/register', {**account, 'name': '模拟学生'+name, 'grade':'初一'})
                token = user['access_token']
                credential = {**account, 'name':name}
                credentials.append(credential)
                accounts.write_text(json.dumps(credentials, ensure_ascii=False, indent=2)+'\n')
                accounts.chmod(0o600)
                question = request('POST', '/questions/manual', {
                    'question_text':'解方程：'+equation, 'student_steps':steps,
                    'student_answer':answer, 'subject':'数学', 'grade':'初一',
                }, token)
                qid = question['id']
                row['question_id'] = credential['question_id'] = qid
                analysis = request('POST', f'/questions/{qid}/analyze', {}, token)
                text = str(analysis.get('final_answer','')).replace(' ', '').replace('$','').replace('＝','=')
                row['answer_correct'] = text in (expected, 'x='+expected)
                row['verified'] = bool(analysis.get('verified'))
                diagnosis = request('POST', f'/questions/{qid}/diagnose', {}, token)
                row['first_error'] = diagnosis.get('first_error_step')
                row['error_type'] = diagnosis.get('error_type')
                row['diagnosis_correct'] = row['first_error'] == first and (
                    first is not None or row['error_type'] in ('exact','equivalent'))
                detail = request('GET', f'/questions/{qid}', token=token)
                row['original_preserved'] = detail['student_answer'] == answer and [s['text'] for s in detail['student_steps']] == steps
                sources = request('GET', '/analytics/error-sources', token=token)
                row['source_owned'] = all(s['id'] == qid for s in sources['sources'])
                row['passed'] = all(row[k] for k in ('answer_correct','verified','diagnosis_correct','original_preserved','source_owned'))
            except (httpx.HTTPError, RuntimeError, KeyError, ValueError) as error:
                row['passed'] = False
                row['failure_kind'] = type(error).__name__
            row['elapsed_seconds'] = round(time.monotonic()-started, 1)
            output.write_text(json.dumps({'kind':'actual-pool-public-samples', 'student_trial':False,
                                           'results':results}, ensure_ascii=False, indent=2)+'\n')
            output.chmod(0o600)
            accounts.write_text(json.dumps(credentials, ensure_ascii=False, indent=2)+'\n')
            print(json.dumps(row, ensure_ascii=False), flush=True)
    if not all(row['passed'] for row in results):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
