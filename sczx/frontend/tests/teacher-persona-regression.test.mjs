import {test} from 'node:test';
import assert from 'node:assert/strict';
import {Browser} from './cdp.mjs';

async function scenario(mode){
 const {createApp,h,nextTick}=await import('/node_modules/.vite/deps/vue.js');
 const {createPinia,getActivePinia,setActivePinia}=await import('/node_modules/.vite/deps/pinia.js');
 const source=await(await fetch('/src/main.js')).text();
 const {createRouter,createMemoryHistory}=await import(source.match(/from ["']([^"']*vue-router\.js[^"']*)/)[1]);
 const {useLearning}=await import('/src/store.js'),{TooltipProvider}=await import('/src/components/ui/tooltip/index.js');
 const {default:Page}=await import(mode==='feedback'?'/src/pages/Insights.vue':'/src/pages/Examinations.vue');
 const prior=getActivePinia(),pinia=createPinia(),store=useLearning(pinia),originalFetch=window.fetch,writes=[];
 const record=(id,name)=>({id:'record-'+id,studentId:id,studentName:name,feedback:'',attempts:[],helps:[],repairs:[],metrics:{},drafts:{blocks:{},questions:{}}});
 const records=[record('one','学生甲'),record('two','学生乙')];
 const task={id:'task-one',classId:'room-b',className:'乙班',title:'共同运算',publishedAt:'2026-11-12T00:00:00Z',questions:[],summary:{}};
 store.user={id:'teacher',role:'teacher'};store.status='ready';store.data.tasks=[task,{...task,id:'task-two'}];store.data.activeTaskId=task.id;store.data.activeStudentId='one';store.data.studentRecords={[task.id]:records};store.data.records={};
 const entry={versionId:'question-one',points:10,question:{prompt:'求解',equation:'x+3=8',answer:'5'}};
 const paper={id:'paper-one',reviewed:true,revision:1,draft:{title:'时区检查',unitId:'unit',entries:[entry],total:10},versions:[{id:'version-one',number:1}]};
 const exam={id:'new-exam',title:'时区检查',startsAt:'2026-11-12T02:00:00Z',endsAt:'2026-11-12T03:00:00Z',minutes:30,paper:{entries:[entry]},submissions:[]};
 window.fetch=(url,options={})=>{
  const path=String(url);if(!path.startsWith('/api/'))return originalFetch(url,options);
  const method=options.method||'GET';if(method!=='GET')writes.push({path,method,body:JSON.parse(options.body||'{}')});
  let value=[];
  if(path==='/api/records/record-two/feedback')value={feedback:JSON.parse(options.body).feedback,feedbackAt:'2026-11-12T01:00:00Z'};
  if(path==='/api/teaching/tasks/task-one')value=task;
  if(path==='/api/exams/papers')value=[paper];
  if(path==='/api/teaching/classes')value=[{id:'room-a',name:'甲班'},{id:'room-b',name:'乙班'}];
  if(path==='/api/curriculum/courses')value=[{units:[{id:'unit',title:'等式',lessons:[]}]}];
  if(path==='/api/exams'&&method==='POST')value=exam;
  if(path==='/api/exams/new-exam')value=exam;
  return Promise.resolve(new Response(JSON.stringify(value),{headers:{'Content-Type':'application/json'}}));
 };
 const router=createRouter({history:createMemoryHistory(),routes:[{path:'/insights',name:'insights',component:Page},{path:'/exam-papers',name:'exam-papers',component:Page},{path:'/exams',name:'exams',component:Page}]});
 await router.push(mode==='feedback'?'/insights?task=task-one':'/exam-papers');await router.isReady();
 const el=document.createElement('div');document.body.append(el);const app=createApp({render:()=>h(TooltipProvider,null,{default:()=>h(Page)})});app.use(pinia);app.use(router);app.provide('notify',()=>{});Object.assign(app._context.components,document.querySelector('#root').__vue_app__._context.components);app.mount(el);
 const wait=async fn=>{for(let i=0;i<150;i++){if(fn())return;await new Promise(r=>setTimeout(r,20))}throw Error('Wait failed: '+el.textContent)};
 try{
  if(mode==='feedback'){
   await wait(()=>el.querySelectorAll('tbody tr button').length===2);el.querySelectorAll('tbody tr button')[1].click();await nextTick();await new Promise(r=>setTimeout(r,100));
   const dialog=document.querySelector('[role=dialog]');const opened=!!dialog&&dialog.textContent.includes('学生乙');
   if(!opened)return{opened,writes};
   const tab=[...dialog.querySelectorAll('[role=tab]')].find(t=>t.textContent==='教师反馈');tab.dispatchEvent(new MouseEvent('mousedown',{button:0,bubbles:true}));tab.focus();await nextTick();
   await wait(()=>document.querySelector('#student-feedback'));
   const input=document.querySelector('#student-feedback');input.value='两边共同运算的解释清楚。';input.dispatchEvent(new Event('input',{bubbles:true}));await nextTick();[...dialog.querySelectorAll('button')].find(b=>b.textContent.trim()==='保存反馈').click();
   await wait(()=>records[1].feedback.length>0);const stayedOpen=!!document.querySelector('[role=dialog]');
   store.selectTask('task-two');await nextTick();await new Promise(r=>setTimeout(r,180));
   return{opened,stayedOpen,closedOnTaskSwitch:!document.querySelector('[role=dialog]'),feedback:records.map(r=>r.feedback),writes};
  }
  await wait(()=>el.querySelector('.teacher-paper-row'));el.querySelector('.teacher-paper-row').click();await nextTick();[...el.querySelectorAll('button')].find(b=>b.textContent.trim()==='发布考试').click();await nextTick();
  await wait(()=>document.querySelector('[role=dialog] input[type=datetime-local]'));
  const dialog=document.querySelector('[role=dialog]'),inputs=dialog.querySelectorAll('input[type=datetime-local]');const initial=inputs[0].value,expected=new Date(Date.now()-60000+8*3600000).toISOString().slice(0,16),labels=dialog.textContent;
  for(let i=0;i<2;i++){inputs[i].value=i?'2026-11-12T11:00':'2026-11-12T10:00';inputs[i].dispatchEvent(new Event('input',{bubbles:true}))}await nextTick();dialog.querySelector('form').requestSubmit();await wait(()=>writes.length>0);
  return{initial,expected,labels,writes,duplicateTabs:!!el.querySelector('.exam-tabs')};
 }finally{app.unmount();el.remove();window.fetch=originalFetch;setActivePinia(prior)}
}
for(const mode of ['feedback','publish'])test(mode==='feedback'?'student selection keeps feedback dialog open; feedback targets the selected record and task changes close it':'exam dates use Beijing input and convert to UTC requests independent of the host timezone',async()=>{
 const b=await Browser.launch();try{await b.goto((process.env.SCZX_TEST_ORIGIN||'http://127.0.0.1:5177')+'/#/login');await b.wait("!!document.querySelector('#root')?.__vue_app__");const r=await b.eval(scenario,mode);
 if(mode==='feedback'){assert(r.opened);assert(r.stayedOpen);assert(r.closedOnTaskSwitch);assert.deepEqual(r.feedback,['','两边共同运算的解释清楚。']);assert.equal(r.writes.length,1);assert.equal(r.writes[0].path,'/api/records/record-two/feedback')}
 else{assert.equal(r.initial,r.expected);assert(r.labels.includes('北京时间'));assert(!r.labels.includes('UTC'));assert.equal(r.writes[0].body.startsAt,'2026-11-12T02:00:00.000Z');assert.equal(r.writes[0].body.endsAt,'2026-11-12T03:00:00.000Z');assert(!r.duplicateTabs)}assert.deepEqual(b.errors,[]);
 }finally{await b.close()}
});
