import {test} from 'node:test';
import assert from 'node:assert/strict';
import {Browser} from './cdp.mjs';

// Browser-mounted components use isolated, in-memory records. No credentials or
// business writes are needed to check the decisions a first-time user faces.
async function workspaceScenario(mode){
  const {createApp,h,nextTick}=await import('/node_modules/.vite/deps/vue.js');
  const {createPinia,getActivePinia,setActivePinia}=await import('/node_modules/.vite/deps/pinia.js');
  const source=await(await fetch('/src/main.js')).text();
  const {createRouter,createMemoryHistory}=await import(source.match(/from ["']([^"']*vue-router\.js[^"']*)/)[1]);
  const {useLearning}=await import('/src/store.js');
  const {default:App}=await import('/src/App.vue');
  const {default:Dashboard}=await import('/src/pages/Dashboard.vue');
  const {default:Lesson}=await import('/src/pages/Lesson.vue');
  const {TooltipProvider}=await import('/src/components/ui/tooltip/index.js');
  const originalFetch=window.fetch,prior=getActivePinia(),url=location.href;
  const pinia=createPinia(),s=useLearning(pinia);
  const task={id:'test-ui-next',title:'补充练习：两边同时减3',className:'测试班',status:'待开始',snapshot:{goal:'说出两边进行的共同运算。',blocks:[]},questions:[{id:'check-one',kind:'check',prompt:'求解并验算',equation:'x+3=8'}]};
  const record={id:'test-ui-record',drafts:{blocks:{},questions:{}},attempts:[],helps:[],repairs:[]};
  s.user={id:'ui-fixture',role:'student',displayName:'界面验证学生'};s.status='ready';
  s.data.tasks=[task];s.data.activeTaskId=task.id;s.data.records={[task.id]:record};s.data.studentRecords={};
  const writes=[];
  window.fetch=(input,options)=>{
    const path=String(input);
    if(path.startsWith('/api/')){
      if(options?.method&&options.method!=='GET')writes.push({path,method:options.method});
      let value=[];
      if(path.startsWith('/api/teaching/dashboard'))value={classes:[],stats:{pending:1,inProgress:0,submitted:0},tasks:[task],recentSubmissions:[]};
      if(path==='/api/memory')value={items:[],recommendations:[]};
      return Promise.resolve(new Response(JSON.stringify(value),{headers:{'Content-Type':'application/json'}}));
    }
    return originalFetch(input,options);
  };
  const placeholder={render:()=>h('h1','当前页面')};
  const router=createRouter({history:createMemoryHistory(),routes:[{path:'/home',name:'home',component:mode==='dashboard'?Dashboard:placeholder},{path:'/learn',name:'learn',component:placeholder},{path:'/memory',name:'memory',component:placeholder}]});
  await router.push('/home');await router.isReady();
  const el=document.createElement('div');document.body.append(el);
  const app=createApp(mode==='lesson'?{render:()=>h(TooltipProvider,null,{default:()=>h(Lesson)})}:App);
  app.use(pinia);app.use(router);app.provide('notify',()=>{});
  Object.assign(app._context.components,document.querySelector('#root').__vue_app__._context.components);
  app.mount(el);
  try{
    await new Promise(r=>setTimeout(r,180));
    if(mode==='shell'){
      const skip=el.querySelector('.skip-link'),before=location.hash;skip.focus();skip.click();
      const skipResult={unchanged:location.hash===before,main:document.activeElement===el.querySelector('main#main-content')};
      el.querySelector('.navigation-more>summary').click();await nextTick();
      const more=el.querySelector('.navigation-more').open&&[...el.querySelectorAll('.navigation-more a')].some(a=>a.textContent.includes('学习记录'));
      el.querySelector('.search-trigger').click();await nextTick();
      const input=document.querySelector('[role=dialog] input');input.value='两边同时减3';input.dispatchEvent(new Event('input',{bubbles:true}));await nextTick();
      const results=[...document.querySelectorAll('.search-results button')];
      const names=results.map(e=>e.textContent.trim());results[0]?.click();
      const destination=location.hash;
      return{skipResult,more,names,destination,writes};
    }
    if(mode==='dashboard'){
      const primary=el.querySelector('.overview-next-actions button');primary.click();const destination=location.hash;
      const completed=[...el.querySelectorAll('[role=tab]')].find(x=>x.textContent==='已提交');
      completed.dispatchEvent(new MouseEvent('mousedown',{button:0,bubbles:true}));completed.focus();await nextTick();await new Promise(r=>setTimeout(r,30));
      return{destination,empty:el.querySelector('.overview-task-panel').textContent,writes};
    }
    if(mode==='lesson'){
      const initial={text:el.textContent,readingMeta:!!el.querySelector('.curriculum-study-meta'),emptyOutline:!!el.querySelector('.curriculum-outline'),practice:!!el.querySelector('.student-practice-task')};
      [...el.querySelectorAll('button')].find(e=>e.textContent.includes('开始独立练习')).click();const destination=location.hash;
      // The same task can later contain reading. Its directory must focus and
      // persist the chosen block without making a formal answer submission.
      task.snapshot.blocks=[{id:'intro',type:'explanation',title:'共同变化',content:'等式两边同时减3。'},{id:'example',type:'example',title:'验算',content:'把x=5代回原式。'}];
      s.data.tasks=[{...task}];await nextTick();await new Promise(r=>setTimeout(r,70));
      [...el.querySelectorAll('button')].find(b=>b.textContent.trim().startsWith('目录')).click();await nextTick();document.querySelector('[role=dialog] .curriculum-outline>button:last-child').click();await nextTick();
      return{initial,destination,selected:{...s.record.drafts.lessonPosition},outline:el.querySelector('.focused-reading .curriculum-block-heading')?.textContent,writes};
    }
    if(mode==='missing'){
      await router.push('/learn?task=missing-task');await nextTick();await new Promise(r=>setTimeout(r,260));
      const heading=el.querySelector('main h1')?.textContent;[...el.querySelectorAll('button')].find(b=>b.textContent.includes('返回首页')).click();
      return{heading,destination:location.hash,writes};
    }
  }finally{window.fetch=originalFetch;app.unmount();el.remove();history.replaceState(null,'',url);setActivePinia(prior)}
}

async function run(mode){const b=await Browser.launch();try{await b.goto((process.env.SCZX_TEST_ORIGIN||'http://127.0.0.1:5177')+'/#/login');await b.viewport(1440,1000);const result=await b.eval(workspaceScenario,mode);assert.deepEqual(b.errors,[]);assert.deepEqual(result.writes,[]);return result}finally{await b.close()}}

test('skip link keeps the current route, more navigation opens, and search uses assigned tasks',async()=>{const r=await run('shell');assert.deepEqual(r.skipResult,{unchanged:true,main:true});assert(r.more);assert(r.names.some(s=>s.includes('补充练习：两边同时减3')));assert.equal(r.destination,'#/learn?task=test-ui-next')});
test('the home next action opens its own task and the empty submitted tab names the right state',async()=>{const r=await run('dashboard');assert.equal(r.destination,'#/check?task=test-ui-next');assert(r.empty.includes('还没有已提交的任务'));assert(!r.empty.includes('当前任务已完成'))});
test('a questions-only task exposes its exercise without an empty reading workspace; directory changes retain task context',async()=>{const r=await run('lesson');assert(r.initial.practice);assert(!r.initial.readingMeta);assert(!r.initial.emptyOutline);assert(r.initial.text.includes('x+3=8'));assert.equal(r.destination,'#/check?task=test-ui-next');assert.equal(r.selected.blockId,'example');assert(r.outline.includes('验算'))});
test('an unknown assigned task gives a recovery action back to the home screen',async()=>{const r=await run('missing');assert.equal(r.heading,'找不到这个页面');assert.equal(r.destination,'#/home')});
