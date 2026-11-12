"""Existing case favorites must survive login and remain private to each teacher."""
import os,secrets,subprocess,sys,unittest,uuid,copy
from pathlib import Path
import httpx
from sqlalchemy import select,func
from sczx_business.main import app
from sczx_business.database import engine,SessionLocal
from sczx_business.models import Account,TeachingCase,CaseVersion,CaseBookmark
from sczx_business.security import hash_password

@unittest.skipUnless(os.getenv('SCZX_RUN_MYSQL_TESTS')=='1','isolated MySQL required')
class CaseBookmarkTests(unittest.IsolatedAsyncioTestCase):
 @classmethod
 def setUpClass(cls):
  assert engine.url.database.startswith('sczx_test_')
  subprocess.run([sys.executable,'-m','sczx_business.commands','migrate'],cwd=Path(__file__).resolve().parents[1],check=True,capture_output=True)
  cls.password=secrets.token_urlsafe(20)
  with SessionLocal.begin() as db:
   for name,role in [('t1','teacher'),('t2','teacher'),('s1','student')]:db.add(Account(id='bookmark-'+name,username='bookmark-'+name,display_name=name,role=role,password_hash=hash_password(cls.password)))
 async def asyncSetUp(self):
  self.c=httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test');self.ids=[]
  with SessionLocal.begin() as db:
   for _ in range(2):
    ident='case-'+uuid.uuid4().hex[:28];self.ids.append(ident);db.add(TeachingCase(id=ident,title='收藏合成案例',content='原文',source='合成',status='published'));db.flush();db.add(CaseVersion(id='v-'+ident,case_id=ident,number=1,data={'title':'收藏合成案例','content':'固定版本原文','source':'合成'}))
  await self.login('t1')
 async def asyncTearDown(self):await self.c.aclose()
 async def login(self,name):self.assertEqual((await self.c.post('/api/auth/login',json={'username':'bookmark-'+name,'password':self.password})).status_code,200)
 async def set(self,ident,selected,status=200):
  r=await self.c.put('/api/ai/cases/'+ident+'/bookmark',json={'selected':selected});self.assertEqual(r.status_code,status,r.text);return r.json()
 async def test_multiple_favorites_relogin_repeat_remove_and_teacher_isolation(self):
  for ident in self.ids:await self.set(ident,True);await self.set(ident,True)
  await self.c.post('/api/auth/logout');await self.login('t1')
  self.assertEqual(set((await self.c.get('/api/ai/case-bookmarks')).json()['favoriteCaseIds']),set(self.ids))
  with SessionLocal() as db:self.assertEqual(db.scalar(select(func.count()).select_from(CaseBookmark).where(CaseBookmark.owner_id=='bookmark-t1',CaseBookmark.case_id.in_(self.ids))),2)
  await self.login('t2');self.assertEqual((await self.c.get('/api/ai/case-bookmarks')).json()['favoriteCaseIds'],[]);await self.set(self.ids[0],True)
  await self.login('t1');await self.set(self.ids[0],False);await self.set(self.ids[0],False);self.assertEqual((await self.c.get('/api/ai/case-bookmarks')).json()['favoriteCaseIds'],[self.ids[1]])
  await self.login('t2');self.assertEqual((await self.c.get('/api/ai/case-bookmarks')).json()['favoriteCaseIds'],[self.ids[0]])
 async def test_invalid_role_and_withdrawn_case_do_not_rewrite_published_version(self):
  ident=self.ids[0]
  with SessionLocal.begin() as db:
   original=copy.deepcopy(db.get(CaseVersion,'v-'+ident).data);db.get(TeachingCase,ident).status='withdrawn'
  await self.set(ident,True,404);await self.set(self.ids[1],'yes',422);await self.login('s1');await self.set(self.ids[1],True,403);self.assertEqual((await self.c.get('/api/ai/case-bookmarks')).status_code,403)
  with SessionLocal() as db:self.assertEqual(db.get(CaseVersion,'v-'+ident).data,original)
