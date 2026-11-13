"""Real account onboarding; only run against an isolated MySQL database."""
import os, uuid, unittest
import httpx
from sczx_business.main import app
from sczx_business.database import engine

@unittest.skipUnless(os.getenv('SCZX_RUN_MYSQL_TESTS')=='1','isolated MySQL required')
class RegistrationTests(unittest.IsolatedAsyncioTestCase):
 async def test_register_login_teacher_add_by_number_and_persistence(self):
  self.assertTrue(engine.url.database.startswith('sczx_test_'))
  prefix='onboard-'+uuid.uuid4().hex[:10]
  async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as teacher, httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as student:
   async def register(client,name,role):
    r=await client.post('/api/auth/register',json={'username':name,'password':'123456','displayName':'教师' if role=='teacher' else '学生','role':role});self.assertEqual(r.status_code,201,r.text);return r.json()['user']
   r=await student.post('/api/auth/register',json={'username':prefix+'short','password':'12345','displayName':'短密码','role':'student'});self.assertEqual(r.status_code,422)
   t=await register(teacher,prefix+'t','teacher');s=await register(student,prefix+'001','student')
   r=await student.post('/api/auth/register',json={'username':prefix+'001','password':'123456','displayName':'重复','role':'student'});self.assertEqual(r.status_code,409)
   r=await student.post('/api/auth/register',json={'username':prefix+'admin','password':'123456','displayName':'越权','role':'admin'});self.assertEqual(r.status_code,422)
   r=await teacher.post('/api/classrooms',json={'name':'真实入班流程','grade':'高一','subject':'英语'});self.assertEqual(r.status_code,201);room=r.json()['id']
   path='/api/classrooms/'+room+'/members'
   r=await teacher.post(path,json={'studentId':prefix+'001'});self.assertEqual(r.status_code,201,r.text)
   r=await teacher.post(path,json={'studentId':prefix+'001'});self.assertEqual(r.status_code,201)
   members=(await teacher.get(path)).json();self.assertEqual([m['id'] for m in members],[s['id']])
   self.assertEqual((await teacher.post(path,json={'studentId':'missing-'+prefix})).status_code,404)
   await student.post('/api/auth/logout');self.assertEqual((await student.get('/api/auth/me')).status_code,401)
   self.assertEqual((await student.post('/api/auth/login',json={'username':prefix+'001','password':'123456'})).status_code,200)
   rooms=(await student.get('/api/teaching/classes')).json();self.assertIn(room,[r['id'] for r in rooms])
   self.assertEqual((await student.post('/api/classrooms',json={'name':'不允许'})).status_code,403)
