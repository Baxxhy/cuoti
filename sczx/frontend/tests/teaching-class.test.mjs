import {test} from 'node:test';
import assert from 'node:assert/strict';
import {Browser} from './cdp.mjs';
test('class switch ignores delayed old responses and empty teacher task records render',async()=>{
 const b=await Browser.launch();try{
 await b.goto((process.env.SCZX_TEST_ORIGIN||'http://127.0.0.1:5175')+'/#/login');
 const result=await b.eval(async()=>{
  const {createApp,h,nextTick}=await import('/node_modules/.vite/deps/vue.js');
  const {createPinia,getActivePinia,setActivePinia}=await import('/node_modules/.vite/deps/pinia.js');
  const source=await (await fetch('/src/pages/Classroom.vue')).text();const {createRouter,createMemoryHistory,RouterView}=await import(source.match(/from ["']([^"']*vue-router\.js[^"']*)/)[1]);
  const {TooltipProvider}=await import('/src/components/app/provider.js');const {default:Page}=await import('/src/pages/Classroom.vue');const {useLearning}=await import('/src/store.js');
  const original=fetch,prior=getActivePinia(),pinia=createPinia(),s=useLearning(pinia);s.user={id:'teacher',role:'teacher'};s.data={classroom:{id:'a'},classrooms:[],records:{},lesson:{id:'l'}};s.save=async()=>true;
  let release,delayed=false;
  const task=id=>({id:'task-'+id,title:'任务'+id,classId:id,className:'班级'+id,summary:{submitted:0,assigned:0,inactive:0,status:'未分配'}});
  window.fetch=(url,opts)=>{
   const path=String(url).split('?')[0];let value=[];
   if(path==='/api/teaching/classes')value=['a','b'].map(id=>({id,name:'班级'+id,grade:'七',subject:'数学'}));
   else if(path.endsWith('/a/tasks')){delayed=true;return new Promise(r=>release=()=>r(new Response(JSON.stringify([task('a')]))))}
   else if(path.endsWith('/b/tasks'))value=[task('b')];
   else if(path==='/api/accounts'||path.endsWith('/members')||path.endsWith('/invites'))value=[];
   else return original(url,opts);
   return Promise.resolve(new Response(JSON.stringify(value)));
  };
  const router=createRouter({history:createMemoryHistory(),routes:[{path:'/class',component:Page}]});await router.push('/class?class=a');await router.isReady();
  const el=document.createElement('div');document.body.append(el);const app=createApp({render:()=>h(TooltipProvider,null,{default:()=>h(RouterView)})});app.use(pinia);app.use(router);app.provide('notify',()=>{});Object.assign(app._context.components,document.querySelector('#root').__vue_app__._context.components);app.mount(el);
  const wait=async fn=>{for(let i=0;i<200;i++){if(fn())return;await new Promise(r=>setTimeout(r,20))}throw Error('Class wait: '+el.textContent)};
  try{
   await wait(()=>delayed);await router.push('/class?class=b');await wait(()=>el.textContent.includes('任务b'));release();await new Promise(r=>setTimeout(r,100));await nextTick();
   return {newTask:el.textContent.includes('任务b'),oldTask:el.textContent.includes('任务a'),unassigned:el.textContent.includes('未分配'),selected:s.currentClassId};
  }finally{window.fetch=original;app.unmount();el.remove();setActivePinia(prior)}
 });assert(result.newTask);assert(!result.oldTask);assert(result.unassigned);assert.equal(result.selected,'b');assert.deepEqual(b.errors,[]);
 }finally{await b.close()}
});
test('leaving the dashboard before its response cannot redirect the next page',async()=>{
 const b=await Browser.launch();try{
 await b.goto((process.env.SCZX_TEST_ORIGIN||'http://127.0.0.1:5175')+'/#/login');
 const result=await b.eval(async()=>{
  const {createApp,h}=await import('/node_modules/.vite/deps/vue.js');const {createPinia,getActivePinia,setActivePinia}=await import('/node_modules/.vite/deps/pinia.js');
  const source=await(await fetch('/src/pages/Dashboard.vue')).text();const {createRouter,createMemoryHistory,RouterView}=await import(source.match(/from ["']([^"']*vue-router\.js[^"']*)/)[1]);const {default:Page}=await import('/src/pages/Dashboard.vue');const {useLearning}=await import('/src/store.js');
  const original=fetch,prior=getActivePinia(),pinia=createPinia(),s=useLearning(pinia);s.user={role:'teacher'};s.data={classroom:{id:'a'},lesson:{id:'l'}};let release;
  window.fetch=(url,opts)=>String(url).startsWith('/api/teaching/dashboard')?new Promise(r=>release=()=>r(new Response(JSON.stringify({classes:[{id:'a',name:'一班'}],selectedClassId:'a',tasks:[],stats:{},recentSubmissions:[]})))):original(url,opts);
  const router=createRouter({history:createMemoryHistory(),routes:[{path:'/teacher',name:'teacher',component:Page},{path:'/insights',component:{render:()=>h('p','学生过程')}}]});await router.push('/teacher');await router.isReady();const el=document.createElement('div');document.body.append(el);const app=createApp({render:()=>h(RouterView)});app.use(pinia);app.use(router);Object.assign(app._context.components,document.querySelector('#root').__vue_app__._context.components);app.mount(el);
  try{for(let i=0;i<100&&!release;i++)await new Promise(r=>setTimeout(r,20));if(!release)throw Error('dashboard did not request');await router.push('/insights?task=b');release();await new Promise(r=>setTimeout(r,150));return{path:router.currentRoute.value.fullPath,text:el.textContent}}finally{window.fetch=original;app.unmount();el.remove();setActivePinia(prior)}
 });assert.equal(result.path,'/insights?task=b');assert.equal(result.text,'学生过程');assert.deepEqual(b.errors,[]);
 }finally{await b.close()}
});
