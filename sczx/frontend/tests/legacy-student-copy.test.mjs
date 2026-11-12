import {test} from 'node:test';
import assert from 'node:assert/strict';
import {Browser} from './cdp.mjs';
test('legacy AI draft offers editable student copy and preview preserves teacher instructions',async()=>{
 const b=await Browser.launch();try{
  await b.goto((process.env.SCZX_TEST_ORIGIN||'http://127.0.0.1:5177')+'/#/login');
  await b.wait("!!document.querySelector('#root')?.__vue_app__");
  const result=await b.eval(async()=>{
   const {createApp,h,nextTick}=await import('/node_modules/.vite/deps/vue.js');
   const {createPinia,getActivePinia,setActivePinia}=await import('/node_modules/.vite/deps/pinia.js');
   const raw=await(await fetch('/src/main.js')).text();
   const {createRouter,createMemoryHistory}=await import(raw.match(/from ["']([^"']*vue-router\.js[^"']*)/)[1]);
   const {useLearning}=await import('/src/store.js'),{default:Prepare}=await import('/src/pages/Prepare.vue'),{TooltipProvider}=await import('/src/components/app/provider.js');
   const prior=getActivePinia(),pinia=createPinia(),s=useLearning(pinia),originalFetch=fetch,writes=[];
   const canonical={id:'legacy-b',type:'explanation',title:'等式性质',content:'等式两边同时加3仍相等。'};
   s.user={id:'teacher-fixture',role:'teacher'};s.status='ready';s.data.lesson={id:'lesson-fixture',title:'测试课时'};
   s.data.lessonDraft={lessonId:'lesson-fixture',goal:'共同运算',blocks:[{...canonical,content:'出示等式，追问两边的变化。',agentJobId:'old-job'}],questions:[],lessonSnapshot:{blocks:[canonical]},caseId:'',caseSnapshot:null,planningDetails:{}};
   s.data.classrooms=[];s.data.tasks=[];
   window.fetch=(url,options)=>String(url).startsWith('/api/')?(options?.method&&options.method!=='GET'&&writes.push(String(url)),Promise.resolve(new Response(JSON.stringify([])))):originalFetch(url,options);
   const router=createRouter({history:createMemoryHistory(),routes:[{path:'/prepare',name:'prepare',component:Prepare}]});await router.push('/prepare');await router.isReady();
   const el=document.createElement('div');document.body.append(el);const app=createApp({render:()=>h(TooltipProvider,null,{default:()=>h(Prepare)})});app.use(pinia);app.use(router);app.provide('notify',()=>{});Object.assign(app._context.components,document.querySelector('#root').__vue_app__._context.components);app.mount(el);
   try{
    await nextTick();const details=[...el.querySelectorAll('details')].find(d=>d.querySelector(':scope > summary')?.textContent==='学生正文');if(!details)throw Error('missing student copy editor');details.open=true;details.dispatchEvent(new Event('toggle'));await nextTick();
    const area=details.querySelector('textarea');const restored=area.value;area.value='等式两边同时减2，等式仍成立。';area.dispatchEvent(new Event('input',{bubbles:true}));await nextTick();
    const {default:Preview}=await import('/src/components/LessonPreview.vue');const pane=document.createElement('div');document.body.append(pane);const preview=createApp({render:()=>h(TooltipProvider,null,{default:()=>h(Preview,{lesson:{...s.data.lessonDraft,title:'学生预览'}})})});preview.use(pinia);Object.assign(preview._context.components,document.querySelector('#root').__vue_app__._context.components);preview.mount(pane);await nextTick();const text=pane.textContent;preview.unmount();pane.remove();
    return{restored,student:s.data.lessonDraft.blocks[0].studentContent,teacher:s.data.lessonDraft.blocks[0].content,preview:text,writes};
   }finally{app.unmount();el.remove();window.fetch=originalFetch;setActivePinia(prior)}
  });
  assert.equal(result.restored,'等式两边同时加3仍相等。');assert.equal(result.student,'等式两边同时减2，等式仍成立。');assert.equal(result.teacher,'出示等式，追问两边的变化。');assert.ok(result.preview.includes(result.student));assert.ok(!result.preview.includes(result.teacher));assert.deepEqual(result.writes,[]);assert.deepEqual(b.errors,[]);
 }finally{await b.close()}
});
