import{test}from'node:test';import assert from'node:assert/strict';import{Browser}from'./cdp.mjs';
async function scenario(mode){
 const {createApp,h,nextTick}=await import('/node_modules/.vite/deps/vue.js');
 const {createPinia,getActivePinia,setActivePinia}=await import('/node_modules/.vite/deps/pinia.js');
 const src=await(await fetch('/src/main.js')).text();const {createRouter,createMemoryHistory}=await import(src.match(/from ["']([^"']*vue-router\.js[^"']*)/)[1]);
 const {useLearning}=await import('/src/store.js'),{TooltipProvider}=await import('/src/components/ui/tooltip/index.js');
 const {default:Page}=await import(mode==='prepare'?'/src/pages/Prepare.vue':'/src/pages/Examinations.vue');
 const prior=getActivePinia(),pinia=createPinia(),s=useLearning(pinia),original=fetch,writes=[];
 s.user={id:'teacher-focus',role:'teacher'};s.status='ready';s.data.lesson={id:'lesson-focus',title:'测试课时'};
 s.data.lessonDraft={lessonId:'lesson-focus',goal:'相同运算',blocks:[{id:'a',title:'第一活动',content:'两边同时加3。',type:'explanation'},{id:'b',title:'第二活动',content:'代回原式。',type:'explanation'}],questions:[],caseId:'',caseSnapshot:null,planningDetails:{}};
 s.data.classrooms=[];s.data.tasks=[];s.save=async()=>true;
 const entries=[1,2].map(i=>({versionId:'q'+i,points:10,question:{prompt:'题目'+i,equation:'x+'+i+'=5',answer:String(5-i),explanation:'两边同时减'+i}}));
 let fail=true;const submission={id:'s1',studentName:'模拟学生',submittedAt:'2026-11-01T00:00:00Z',revision:1,answers:{q1:{answer:'4',reason:'两边减1'},q2:{answer:'3',reason:'两边减2'}},grades:{},automatic:{},total:0,audits:[]};
 const exam={id:'focus-exam',title:'两题检查',startsAt:'2026-11-01T00:00:00Z',endsAt:'2026-12-01T00:00:00Z',minutes:30,resultsAt:null,paper:{entries,total:20},submissions:[submission]};
 window.fetch=(url,options)=>{
  const path=String(url);if(!path.startsWith('/api/'))return original(url,options);
  const method=options?.method||'GET';if(method!=='GET')writes.push({path,method,body:JSON.parse(options.body||'{}')});
  if(path.endsWith('/grades')){if(fail){fail=false;return Promise.resolve(new Response(JSON.stringify({detail:'请重新读取后重试'}),{status:409}))}submission.grades=JSON.parse(options.body).grades;submission.revision++;}
  let value=[];
  if(path==='/api/exams/focus-exam')value=exam;
  return Promise.resolve(new Response(JSON.stringify(value),{headers:{'Content-Type':'application/json'}}));
 };
 const router=createRouter({history:createMemoryHistory(),routes:[{path:'/prepare',component:Page},{path:'/exams',component:Page}]});await router.push(mode==='prepare'?'/prepare':'/exams?exam=focus-exam');await router.isReady();
 const el=document.createElement('div');document.body.append(el);const app=createApp({render:()=>h(TooltipProvider,null,{default:()=>h(Page)})});app.use(pinia);app.use(router);app.provide('notify',()=>{});Object.assign(app._context.components,document.querySelector('#root').__vue_app__._context.components);app.mount(el);
 const wait=async fn=>{for(let i=0;i<150;i++){await new Promise(r=>setTimeout(r,20));if(fn())return}throw Error('wait: '+el.textContent)};
 try{
  if(mode==='prepare'){
   await wait(()=>el.querySelector('#activity-content'));const count=el.querySelectorAll('#activity-content').length;
   const input=el.querySelector('#activity-content');input.value='未保存的第一活动修改';input.dispatchEvent(new Event('input',{bubbles:true}));await nextTick();
   el.querySelectorAll('.focus-activity-item>button:last-child')[1].click();await nextTick();const second=el.querySelector('#activity-content').value;
   el.querySelectorAll('.focus-activity-item>button:last-child')[0].click();await nextTick();return{count,second,restored:el.querySelector('#activity-content').value,writes};
  }
  await wait(()=>el.querySelector('.exam-grade-question input'));const originalAnswers=JSON.stringify(submission.answers);
  const input=el.querySelector('.exam-grade-question input');input.value='8';input.dispatchEvent(new Event('input',{bubbles:true}));await nextTick();
  const save=()=>[...el.querySelectorAll('button')].find(b=>b.textContent.trim()==='保存并下一题').click();save();
  await wait(()=>el.querySelector('[role=alert]'));const retained={question:el.querySelector('.exam-grade-question h3').textContent,score:el.querySelector('.exam-grade-question input').value};save();
  await wait(()=>el.querySelector('.exam-grade-question h3')?.textContent.startsWith('2.'));
  return{one:el.querySelectorAll('.exam-grade-question').length,retained,advanced:el.querySelector('.exam-grade-question h3').textContent,grade:submission.grades.q1,answersUnchanged:JSON.stringify(submission.answers)===originalAnswers,writes};
 }finally{app.unmount();el.remove();window.fetch=original;setActivePinia(prior)}
}
for(const mode of ['prepare','grade'])test(mode==='prepare'?'switching a focused activity retains unsaved edits without writes':'failed focused grading stays on question; successful save moves next and preserves original answers',async()=>{
 const b=await Browser.launch();try{await b.goto((process.env.SCZX_TEST_ORIGIN||'http://127.0.0.1:5177')+'/#/login');await b.wait("!!document.querySelector('#root')?.__vue_app__");const r=await b.eval(scenario,mode);
 if(mode==='prepare'){assert.equal(r.count,1);assert.equal(r.second,'代回原式。');assert.equal(r.restored,'未保存的第一活动修改');assert.deepEqual(r.writes,[])}else{assert.equal(r.one,1);assert.ok(r.retained.question.startsWith('1.'));assert.equal(r.retained.score,'8');assert.ok(r.advanced.startsWith('2.'));assert.equal(r.grade.score,8);assert(r.answersUnchanged);assert.equal(r.writes.length,2)}assert.deepEqual(b.errors,[]);
 }finally{await b.close()}
});
