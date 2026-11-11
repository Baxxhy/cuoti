import {readFileSync,writeFileSync} from 'node:fs';
import {Browser,sleep} from '/root/Baxxhy/zhiwei/sczx/frontend/tests/cdp.mjs';
const out='/tmp/sczx-step18', cfg=JSON.parse(readFileSync(out+'/private.json')),t=await Browser.launch(),s=await Browser.launch(),report={screens:[]};
async function login(b,user){await b.viewport(1920);await b.goto('http://127.0.0.1:8091/#/login');await b.eval(async({user,password})=>{await fetch('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:user,password})})} ,{user,password:cfg.password});await b.send('Page.reload');await sleep(650)}
async function api(b,path,method='GET',body){return b.eval(async({path,method,body})=>{const r=await fetch('/api'+path,{method,...(body?{headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{})});if(!r.ok)throw Error(await r.text());return r.json()},{path,method,body})}
try{
 await login(t,'unit-t1');await login(s,'unit-s0');
 let classroom=await api(t,'/live','POST',{classId:'unit-c0',lessonId:'lesson-equation'});report.id=classroom.id;
 await api(s,'/live/'+classroom.id+'/join','POST',{});
 classroom=await api(t,'/live/'+classroom.id+'/push','POST',{revision:classroom.revision,question:0});
 await api(s,'/live/'+classroom.id+'/activities/'+classroom.currentId+'/answer','PUT',{revision:0,answer:'8',reason:'断网前保存的原始解释',submit:false});
 await s.eval(id=>location.hash='/live?session='+id,classroom.id);await s.wait("document.querySelector('.teaching-label input')?.value==='8'");
 await s.send('Network.enable');await s.send('Network.emulateNetworkConditions',{offline:true,latency:0,downloadThroughput:0,uploadThroughput:0});
 await s.eval(()=>document.querySelector('[aria-label="刷新课堂"]').click());await s.wait("!!document.querySelector('[role=alert]')");
 report.offline={error:await s.eval(()=>document.querySelector('[role=alert]').textContent),answer:await s.eval(()=>document.querySelector('.teaching-label input').value)};
 await s.send('Network.emulateNetworkConditions',{offline:false,latency:0,downloadThroughput:-1,uploadThroughput:-1});await s.eval(()=>document.querySelector('[aria-label="刷新课堂"]').click());await s.wait("!document.querySelector('[role=alert]')");await s.send('Page.reload');await sleep(500);await s.wait("document.querySelector('.teaching-label input')?.value==='8'");
 report.restored=await api(s,'/live/'+classroom.id);report.savedReason=report.restored.activities[0].answer.reason;
 if(report.savedReason!=='断网前保存的原始解释')throw Error('saved data lost');
 classroom=await api(t,'/live/'+classroom.id);await api(t,'/live/'+classroom.id+'/end','POST',{revision:classroom.revision});
 report.memory=await api(s,'/memory');const equality=report.memory.items.find(i=>i.id==='kp-equality');
 if(!equality?.evidence.some(e=>e.source==='live-class'||e.title?.includes('课堂')||e.taskId===JSON.parse(readFileSync(out+'/live-browser.json')).ended.taskId))throw Error('missing classroom evidence');
 for(const[b,role,url]of[[s,'student','/memory?knowledge=kp-equality'],[t,'teacher','/memory?studentId=unit-s0&classId=unit-c0&knowledge=kp-equality']]){
  await b.eval(url=>location.hash=url,url);await b.wait("document.body.innerText.includes('等式性质')");await sleep(500);
  for(const width of[1440,1920,2560]){await b.viewport(width);await b.screenshot(out+'/'+role+'-memory-'+width+'.png');const size=await b.eval(()=>({scroll:document.documentElement.scrollWidth,client:document.documentElement.clientWidth}));if(size.scroll>size.client+1)throw Error('memory overflow');report.screens.push({role,width,...size})}
 }
 report.consoleErrors=[...t.errors,...s.errors];if(report.consoleErrors.length)throw Error(JSON.stringify(report.consoleErrors));report.passed=true;console.log('actual network offline/online/reload and shared teacher/student memory PASS');
}catch(e){report.failure=e.message;throw e}finally{writeFileSync(out+'/recovery-memory.json',JSON.stringify(report,null,2));await Promise.all([t.close(),s.close()])}
