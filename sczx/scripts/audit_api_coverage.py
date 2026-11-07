"""Trace real TestClient HTTP outcomes during backend checks, without payloads.

A traced request proves that outcome was exercised by a passing test. It does not
prove all branches or semantic equivalence merely because a route was requested.
"""
import json
from pathlib import Path
import re
import secrets
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
import httpx
import pytest
from starlette.routing import Match
from starlette.testclient import TestClient


class Audit:
    def __init__(self):
        self.current=None;self.requests=[];self.outcomes={};self.registered={}
    def pytest_runtest_setup(self,item):self.current=item.nodeid
    def pytest_runtest_logreport(self,report):
        if report.when=='call':self.outcomes[report.nodeid]=report.outcome
    def trace(self,client,request,response):
        if not isinstance(client,TestClient):return
        scope={'type':'http','path':request.url.path,'method':request.method,'root_path':''}
        for route in client.app.routes:
            if not getattr(route,'methods',None):continue
            self.registered[route.path]=sorted(route.methods)
        for route in client.app.routes:
            match,_=route.matches(scope)
            if match==Match.FULL:
                self.requests.append({'test':self.current,'path':route.path,'method':request.method,'status':response.status_code})
                return


def main():
    destination=ROOT/'.runtime/api-audit'/secrets.token_hex(4);destination.mkdir(parents=True)
    audit=Audit();send=httpx.Client.send
    def traced(client,request,*args,**kwargs):
        response=send(client,request,*args,**kwargs)
        audit.trace(client,request,response)
        return response
    httpx.Client.send=traced
    try:result=pytest.main([str(ROOT/'backend/tests'),'-q'],plugins=[audit])
    finally:httpx.Client.send=send
    inventory=json.loads((ROOT/'api_parity_inventory.json').read_text())
    canonical=lambda value:re.sub(r'\{[^}]+:path\}', '*',value)
    valid=[row for row in audit.requests if audit.outcomes.get(row['test'])=='passed']
    rows=[]
    for item in inventory:
        actual=[(path,methods) for path,methods in audit.registered.items() if canonical(path)==item['path']]
        requests=[row for row in valid if canonical(row['path'])==item['path']]
        methods=[]
        for method in item['python_methods']:
            matching=[row for row in requests if row['method']==method]
            methods.append({'method':method,'registered':any(method in allowed for _,allowed in actual),'success_tests':sorted({row['test'] for row in matching if 200<=row['status']<300}),'statuses':sorted({row['status'] for row in matching}),'tests':sorted({row['test'] for row in matching})})
        rows.append({'path':item['path'],'source':item['source'],'methods':methods})
    missing=[{'path':row['path'],'method':method['method']} for row in rows for method in row['methods'] if not method['success_tests']]
    unregistered=[{'path':row['path'],'method':method['method']} for row in rows for method in row['methods'] if not method['registered']]
    report={'scope':'passing backend tests and traced HTTP outcomes; not full branch-equivalence proof','pytest_exit_code':int(result),'test_outcomes':{kind:sum(value==kind for value in audit.outcomes.values()) for kind in ['passed','failed','skipped']},'inventory_paths':len(rows),'inventory_methods':sum(len(row['methods']) for row in rows),'traced_passing_test_requests':len(valid),'missing_success_evidence':missing,'unregistered':unregistered,'routes':rows}
    (destination/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({key:value for key,value in report.items() if key!='routes'},ensure_ascii=False))
    print('Report: '+str(destination/'report.json'))
    return int(result) or (1 if unregistered else 0)

if __name__=='__main__':raise SystemExit(main())
