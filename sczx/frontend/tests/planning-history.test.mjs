import {test} from 'node:test';
import assert from 'node:assert/strict';
import {Browser} from './cdp.mjs';
test('agent history follows route, rejects stale replies, guards edits and restores back navigation',async()=>{
 const browser=await Browser.launch();try{
 await browser.goto((process.env.SCZX_TEST_ORIGIN||'http://127.0.0.1:5177')+'/#/login');
 const result=await browser.eval(async()=>{
  const {createApp,h,nextTick}=await import('/node_modules/.vite/deps/vue.js');
  const {createPinia,getActivePinia,setActivePinia}=await import('/node_modules/.vite/deps/pinia.js');
  const {createRouter,createMemoryHistory,RouterView}=await import((await (await fetch('/src/pages/PlanningAgent.vue')).text()).match(/from ["']([^"']*vue-router\.js[^"']*)/)[1]);
  const {TooltipProvider}=await import('/src/components/app/provider.js');
  const {default:Page}=await import('/src/pages/PlanningAgent.vue');const {useLearning}=await import('/src/store.js');
  const original=fetch,oldConfirm=confirm,prior=getActivePinia(),pinia=createPinia();const s=useLearning(pinia);s.data.lesson={id:'one'};s.save=async()=>true;
  const jobs=Object.fromEntries(['a','b','c'].map(id=>[id,{id,capability:'lesson_agent',status:id==='c'?'cancelled':'succeeded',attemptNumber:1,input:{lesson:{versionId:'v1'},lessonId:id==='c'?'two':'one',task:'任务'+id,taskType:'activity',constraints:''},result:{steps:[],cases:[],materials:[],editable:{title:'结果'+id,goal:'目标'+id,rationale:[],blocks:[{id:'block',title:'活动'+id,content:'内容'+id,evidenceIds:[]}],mathClaims:[]}}}]));
  let releaseB,asked=0,allow=false;
  window.confirm=()=>{asked++;return allow};
  window.fetch=(url,opts)=>{
   const path=new URL(String(url),location.origin).pathname;
   let data;
   if(path==='/api/ai/jobs')data=Object.values(jobs);
   else if(path.startsWith('/api/ai/jobs/')){const id=path.split('/').pop();if(id==='b')return new Promise(r=>releaseB=()=>r(new Response(JSON.stringify(jobs.b))));data=jobs[id]}
   else if(path==='/api/curriculum/courses')data=[];
   else if(path.startsWith('/api/curriculum/lessons/'))data={title:'课时',version:1,versionId:'v1',goal:'课时目标'};
   else return original(url,opts);
   return Promise.resolve(new Response(JSON.stringify(data)));
  };
  const router=createRouter({history:createMemoryHistory(),routes:[{path:'/agent',component:Page}]});await router.push('/agent?lesson=one&job=a');await router.isReady();
  const el=document.createElement('div');document.body.append(el);const app=createApp({render:()=>h(TooltipProvider,null,{default:()=>h(RouterView)})});app.use(pinia);app.use(router);Object.assign(app._context.components,document.querySelector('#root').__vue_app__._context.components);app.mount(el);
  const wait=async fn=>{for(let i=0;i<200;i++){if(fn())return;await new Promise(r=>setTimeout(r,20))}throw Error('Controlled history wait: '+el.textContent)};
  try{
   await wait(()=>el.querySelector('#agent-goal')?.value==='目标a');
   const goal=el.querySelector('#agent-goal');goal.value='教师未保存';goal.dispatchEvent(new Event('input',{bubbles:true}));await nextTick();
   await router.push('/agent?lesson=one&job=b');if(router.currentRoute.value.query.job!=='a')throw Error('dirty guard failed');const retained=el.querySelector('#agent-goal').value==='教师未保存';
   allow=true;await router.push('/agent?lesson=one&job=b');await wait(()=>!!releaseB);
   await router.push('/agent?lesson=two&job=c');await wait(()=>el.querySelector('#agent-goal')?.value==='目标c');releaseB();await new Promise(r=>setTimeout(r,100));const noStale=el.querySelector('#agent-goal').value==='目标c';
   await router.push('/agent?lesson=one&job=a');await wait(()=>el.querySelector('#agent-goal')?.value==='目标a');router.back();await wait(()=>el.querySelector('#agent-goal')?.value==='目标c');
   return {retained,noStale,asked,back:true,cancelledVisible:el.textContent.includes('已取消')};
  }finally{window.fetch=original;window.confirm=oldConfirm;app.unmount();el.remove();setActivePinia(prior)}
 });assert(result.retained);assert(result.noStale);assert(result.asked>=2);assert(result.back);assert(result.cancelledVisible);
 }finally{await browser.close()}
});
