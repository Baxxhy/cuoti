"""Opt-in MySQL integration. Refuses to run against the real sczx database."""
import asyncio,copy,json,os,secrets,subprocess,sys,unittest
from pathlib import Path
import httpx
from sqlalchemy import select
from sczx_business.database import engine,SessionLocal
from sczx_business.models import Account,KnowledgePoint,CaseVersion,LearningTask
from sczx_business.security import hash_password
from sczx_business.main import app

@unittest.skipUnless(os.getenv('SCZX_RUN_MYSQL_TESTS')=='1','set SCZX_RUN_MYSQL_TESTS=1 with isolated SCZX_DATABASE_URL')
class MySQLApiTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        assert engine.url.database.startswith('sczx_test_'), 'Tests require an isolated sczx_test_* database'
        root=Path(__file__).resolve().parents[1]
        subprocess.run([sys.executable,'-m','sczx_business.commands','migrate'],cwd=root,check=True,capture_output=True)
        cls.password=secrets.token_urlsafe(24)
        with SessionLocal.begin() as db:
            for role in ['admin','teacher','student']:
                db.add(Account(id='test-'+role,username='test-'+role,display_name='集成验收'+role,role=role,password_hash=hash_password(cls.password)))
            db.add(KnowledgePoint(id='a',name='相等关系',aliases=[],prerequisites=[]))
            db.add(KnowledgePoint(id='b',name='等式性质',aliases=[],prerequisites=['a']))
    async def asyncSetUp(self):
        self.client=httpx.AsyncClient(transport=httpx.ASGITransport(app=app,raise_app_exceptions=False),base_url='http://test')
        await self.login('admin')
    async def asyncTearDown(self):await self.client.aclose()
    async def login(self,role):
        r=await self.client.post('/api/auth/login',json={'username':'test-'+role,'password':self.password});r.raise_for_status()
    async def test_invalid_knowledge_has_no_partial_writes(self):
        before=(await self.client.get('/api/curriculum/knowledge')).json()
        for point in [{'id':[],'name':'异常'},{'id':'bad','name':{}},{'id':'bad','name':False},{'id':'bad','name':'异常','prerequisites':[[]]},{'id':'bad','name':'异常','aliases':[None]}]:
            r=await self.client.put('/api/curriculum/knowledge',json={'points':before+[point]})
            self.assertEqual(r.status_code,422,(point,r.text))
            self.assertEqual((await self.client.get('/api/curriculum/knowledge')).json(),before)
        for points in [[{**p,'prerequisites':['missing']} for p in before],[{**p,'prerequisites':['b'] if p['id']=='a' else ['a']} for p in before]]:
            r=await self.client.put('/api/curriculum/knowledge',json={'points':points});self.assertEqual(r.status_code,422)
    async def test_roles_cannot_write_knowledge(self):
        for role in ['student','teacher']:
            await self.login(role)
            r=await self.client.put('/api/curriculum/knowledge',json={'points':[{'id':'a','name':'相等关系'}]});self.assertEqual(r.status_code,403)
    async def test_revision_and_withdrawal_preserve_history(self):
        base='/api/library/cases';r=await self.client.post(base,json={});self.assertEqual(r.status_code,201);ident=r.json()['id'];path=base+'/'+ident
        data={'title':'持久集成自编验收','content':'等式两边共同变化','legacy':True,'references':[],'knowledgeIds':['b'],'experience':{}}
        async def save_publish(value):
            r=await self.client.put(path+'/draft',json={'data':value});self.assertEqual(r.status_code,200,r.text)
            r=await self.client.post(path+'/review');self.assertEqual(r.status_code,200)
            r=await self.client.post(path+'/publish');self.assertEqual(r.status_code,200,r.text);return r.json()['published']
        v1=await save_publish(data);await self.client.post(path+'/revise')
        modified={**data,'content':'第二版：两边同时加相同的数'}
        r=await self.client.put(path+'/draft',json={'data':modified});self.assertEqual(r.status_code,200)
        historical=(await self.client.get('/api/ai/cases/'+ident,params={'versionId':v1['versionId']})).json();self.assertEqual(historical,v1)
        v2=await save_publish(modified);self.assertNotEqual(v1['versionId'],v2['versionId'])
        await self.client.post(path+'/withdraw')
        self.assertEqual((await self.client.get('/api/ai/cases/'+ident)).status_code,404)
        self.assertEqual((await self.client.get('/api/ai/cases/'+ident,params={'versionId':v1['versionId']})).json(),v1)

if __name__=='__main__':unittest.main()
