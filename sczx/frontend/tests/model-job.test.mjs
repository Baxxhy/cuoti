import {test} from 'node:test';
import assert from 'node:assert/strict';
import {Browser} from './cdp.mjs';
const origin=process.env.SCZX_TEST_ORIGIN||'http://127.0.0.1:5175';
async function run(code){const b=await Browser.launch();try{await b.goto(origin+'/#/login');return await b.eval(code)}finally{await b.close()}}

test('clearing a pending create prevents the old job from reopening',async()=>{
 const result=await run(async()=>{
  const {createApp,h}=await import('/node_modules/.vite/deps/vue.js');const {useModelJob}=await import('/src/lib/useModelJob.js');const original=window.fetch;let release,requested;const ready=new Promise(r=>requested=r);const fixture={id:'controlled-old',status:'succeeded',attemptNumber:1};window.fetch=(url,opts)=>String(url).endsWith('/api/ai/jobs')?new Promise(r=>{release=()=>r(new Response(JSON.stringify(fixture),{status:201}));requested()}):String(url).endsWith('/api/ai/jobs/'+fixture.id)?Promise.resolve(new Response(JSON.stringify(fixture))):original(url,opts);let control;const el=document.createElement('div');document.body.append(el);const app=createApp({setup(){control=useModelJob();return()=>h('div')}});app.mount(el);try{const request=control.create({capability:'retrieval',data:{query:'old'}});await ready;await control.open(null);release();await request;return {job:control.job.value,error:control.error.value}}finally{window.fetch=original;app.unmount();el.remove()}
 });assert.equal(result.job,null);assert.equal(result.error,'');
});

test('SSE terminal status waits for detail; completion callback is idempotent',async()=>{
 const result=await run(async()=>{
  const {createApp,h}=await import('/node_modules/.vite/deps/vue.js');const {useModelJob}=await import('/src/lib/useModelJob.js');const original=window.fetch,OriginalSource=window.EventSource;let source,release,call=0,done=0;window.EventSource=class{constructor(){source=this;this.handlers={}}addEventListener(key,cb){this.handlers[key]=cb}close(){}};const fixture={id:'controlled-sse',status:'running',attemptNumber:1};window.fetch=(url,opts)=>String(url).endsWith('/api/ai/jobs/'+fixture.id)?(++call===1?Promise.resolve(new Response(JSON.stringify(fixture))):new Promise(r=>release=()=>r(new Response(JSON.stringify({...fixture,status:'succeeded',result:{items:[]}}))))):original(url,opts);let control;const el=document.createElement('div');document.body.append(el);const app=createApp({setup(){control=useModelJob(()=>done++);return()=>h('div')}});app.mount(el);try{await control.open(fixture);source.handlers.progress({data:JSON.stringify({...fixture,status:'succeeded'})});await new Promise(r=>setTimeout(r,50));const busyBeforeDetail=control.busy.value;release();await new Promise(r=>setTimeout(r,100));return {busyBeforeDetail,done,status:control.job.value.status,hasResult:!!control.job.value.result}}finally{window.fetch=original;window.EventSource=OriginalSource;app.unmount();el.remove()}
 });assert.equal(result.busyBeforeDetail,true);assert.equal(result.done,1);assert.equal(result.status,'succeeded');assert.equal(result.hasResult,true);
});

test('assistant initialization cannot replace a newer user request',async()=>{
 const result=await run(async()=>{
  const {createApp,h,nextTick}=await import('/node_modules/.vite/deps/vue.js');
  const {createPinia,getActivePinia,setActivePinia}=await import('/node_modules/.vite/deps/pinia.js');
  const {useLearning}=await import('/src/store.js');const {default:Assistant}=await import('/src/components/ModelAssistant.vue');
  const {default:Button}=await import('/src/components/app/Button.vue');const {default:Textarea}=await import('/src/components/app/Textarea.vue');
  const {TooltipProvider}=await import('/src/components/app/provider.js');const {default:Status}=await import('/src/components/app/Status.vue');const {default:InfoTip}=await import('/src/components/app/InfoTip.vue');
  const priorPinia=getActivePinia(),pinia=createPinia(),s=useLearning(pinia);s.status='ready';s.user={role:'student'};s.data.tasks=[{id:'task-a',questions:[]}];s.data.activeTaskId='task-a';s.data.records={'task-a':{id:'record-a',drafts:{},attempts:[],helps:[]}};s.refreshRecord=async()=>{};
  const original=fetch;let release,observed;const ready=new Promise(r=>observed=r);
  const current={id:'current-text',recordId:'record-a',question:0,capability:'text',status:'succeeded',attemptNumber:1,result:{title:'新请求的指导',hint:'比较左右两边',steps:['共同加3'],question:'两边还相等吗？',sources:[]}};
  window.fetch=(url,opts)=>String(url).includes('/api/ai/jobs?recordId=')?new Promise(r=>{release=()=>r(new Response(JSON.stringify([{id:'old-ocr',recordId:'record-a',question:0,capability:'ocr',status:'succeeded'}])));observed()}):String(url).endsWith('/api/ai/jobs')&&opts?.method==='POST'?Promise.resolve(new Response(JSON.stringify(current),{status:201})):String(url).endsWith('/api/ai/jobs/current-text')?Promise.resolve(new Response(JSON.stringify(current))):String(url).endsWith('/api/ai/jobs/old-ocr')?Promise.resolve(new Response(JSON.stringify({id:'old-ocr',recordId:'record-a',question:0,capability:'ocr',status:'succeeded',attemptNumber:1,result:{text:'旧识别覆盖',equation:'',studentAnswer:''}}))):String(url).endsWith('/api/platform')?Promise.resolve(new Response('{}')):original(url,opts);
  const el=document.createElement('div');document.body.append(el);const app=createApp({setup:()=>()=>h(TooltipProvider,null,{default:()=>h(Assistant,{question:0})})});app.use(pinia);for(const [name,component] of Object.entries({AppButton:Button,Textarea,Status,InfoTip}))app.component(name,component);app.mount(el);
  try{await ready;const input=el.querySelector('#learning-question');input.value='为什么两边要同时加3？';input.dispatchEvent(new Event('input',{bubbles:true}));await nextTick();[...el.querySelectorAll('button')].find(b=>b.textContent.trim()==='发送').click();for(let i=0;i<100&&!el.textContent.includes('新请求的指导');i++)await new Promise(r=>setTimeout(r,20));release();await new Promise(r=>setTimeout(r,100));return {newRequestVisible:el.textContent.includes('新请求的指导'),oldOCRVisible:!!el.querySelector('#confirmed-question')}}finally{window.fetch=original;app.unmount();el.remove();setActivePinia(priorPinia)}
 });assert.equal(result.newRequestVisible,true);assert.equal(result.oldOCRVisible,false);
});

test('a delayed platform save cannot attach its revision to another lesson',async()=>{
 const result=await run(async()=>{
  const {createPinia,getActivePinia,setActivePinia}=await import('/node_modules/.vite/deps/pinia.js');const {useLearning}=await import('/src/store.js');const {api}=await import('/src/services/api.js');const old=api.savePlatform,prior=getActivePinia(),s=useLearning(createPinia());let release,calls=0;
  s.data.lessonDraft={id:'old',revision:1};const first=s.data;api.savePlatform=()=>{calls++;return new Promise(r=>release=r)};
  try{const pending=s.save();s.data={...s.data,lessonDraft:{id:'new',revision:7}};s.revision++;release({draftRevision:2});await pending;return {newRevision:s.data.lessonDraft.revision,oldRevision:first.lessonDraft.revision,calls}}finally{api.savePlatform=old;setActivePinia(prior)}
 });assert.equal(result.newRevision,7);assert.equal(result.oldRevision,2);assert.equal(result.calls,1);
});
