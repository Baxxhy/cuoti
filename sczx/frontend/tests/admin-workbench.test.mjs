import {test} from 'node:test';
import assert from 'node:assert/strict';
import {Browser} from './cdp.mjs';
const origin=process.env.SCZX_TEST_ORIGIN||'http://127.0.0.1:5175';

test('material parsing reaches a terminal notice without overwriting a newer save; saved case selection survives leaving the workbench',async()=>{
 const browser=await Browser.launch();try{
 await browser.goto(origin+'/#/login');await browser.wait('!!document.querySelector("#root").__vue_app__');
 const result=await browser.eval(async()=>{
  const {createApp,h,nextTick}=await import('/node_modules/.vite/deps/vue.js');
  const {createPinia,getActivePinia,setActivePinia}=await import('/node_modules/.vite/deps/pinia.js');
  const {createRouter,createMemoryHistory,RouterView}=await import((await (await fetch('/src/components/MaterialWorkbench.vue')).text()).match(/from ["']([^"']*vue-router\.js[^"']*)/)[1]);
  const {TooltipProvider}=await import('/src/components/app/provider.js');
  const {default:Page}=await import('/src/components/MaterialWorkbench.vue');
  const {useLearning}=await import('/src/store.js');const {libraryApi}=await import((await (await fetch('/src/components/MaterialWorkbench.vue')).text()).match(/from ["']([^"']*services\/library\.js[^"']*)/)[1]);const {curriculumApi}=await import('/src/services/curriculum.js');
  const prior=getActivePinia(),pinia=createPinia(),store=useLearning(pinia),oldLibrary={...libraryApi},oldKnowledge=curriculumApi.knowledge;
  store.user={id:'controlled-admin-workbench',role:'admin'};
  const key='sczx:library-context:'+store.user.id;sessionStorage.removeItem(key);
  let state='processing';
  const material=()=>({id:'material-controlled',title:'受控上传材料',status:state,ready:state==='ready'?1:0,total:1,metadata:{author:'',grade:'七年级',subject:'数学'},units:[{id:'unit-controlled',label:'第1段',text:'共同减去3',status:'ready'}]});
  const savedCase={id:'case-controlled',status:'draft',versions:[],draft:{title:'已保存的案例标题',content:'方程两边同时减去3。',reviewed:false,experience:{steps:'旧格式的步骤文字'},references:[]}};
  Object.assign(libraryApi,{coverage:async()=>null,materials:async()=>[material()],material:async()=>material(),unit:async()=>({metadata:{},materialTitle:'受控材料',label:'第1段',text:'共同减去3',originalText:'共同减去3',originalUrl:'#'}),cases:async()=>[savedCase],case:async()=>structuredClone(savedCase),jobs:async()=>[],upload:async()=>material(),newCase:async()=>savedCase,saveMaterial:async()=>material()});
  curriculumApi.knowledge=async()=>[];
  const router=createRouter({history:createMemoryHistory(),routes:[{path:'/manage',component:Page},{path:'/away',component:{render:()=>h('div','其他页面')}}]});await router.push('/manage');await router.isReady();
  const el=document.createElement('div');document.body.append(el);const app=createApp({render:()=>h(TooltipProvider,null,{default:()=>h(RouterView)})});app.use(pinia);app.use(router);Object.assign(app._context.components,document.querySelector('#root').__vue_app__._context.components);app.mount(el);
  const wait=async(fn,timeout=10000)=>{const end=Date.now()+timeout;while(Date.now()<end){if(fn())return;await new Promise(r=>setTimeout(r,30))}throw Error('Admin workbench wait: '+el.textContent)};
  const click=async(label,scope=el)=>{const b=[...scope.querySelectorAll('button,[role=tab]')].find(b=>b.textContent.trim()===label);if(!b)throw Error('Missing button '+label);b.dispatchEvent(new MouseEvent('mousedown',{button:0,bubbles:true}));b.click();await nextTick()};
  try{
   await wait(()=>el.textContent.includes('受控上传材料'));
   await click('上传材料');await wait(()=>document.querySelector('#material-file'));
   const input=document.querySelector('#material-file'),files=new DataTransfer();files.items.add(new File(['共同减去3'],'受控材料.docx',{type:'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}));input.files=files.files;input.dispatchEvent(new Event('change',{bubbles:true}));await nextTick();await click('上传并解析',document.querySelector('[role="dialog"]'));
   await wait(()=>el.textContent.includes('原文件已保存，正在解析'));state='ready';await wait(()=>el.textContent.includes('原文件已保存，解析完成'));
   const terminalNotice=el.textContent.includes('解析完成')&&!el.textContent.includes('正在解析');
   await click('编辑信息');await click('保存信息',document.querySelector('[role="dialog"]'));await wait(()=>el.textContent.includes('材料信息已保存'));await new Promise(r=>setTimeout(r,3200));const newerNotice=el.textContent.includes('材料信息已保存')&&!el.textContent.includes('原文件已保存，解析完成');
   await click('整理成案例');await click('手动整理');await wait(()=>el.querySelector('#case-title')?.value===savedCase.draft.title);await router.push('/away');await nextTick();await router.push('/manage');await wait(()=>el.querySelector('#case-title')?.value===savedCase.draft.title);
   const restored=el.querySelector('#case-title').value;await click('出处');await wait(()=>el.textContent.includes('来源类型'));const provenanceVisible=el.textContent.includes('授权依据');await click('正文');await click('预览');await wait(()=>document.querySelector('.case-preview-title'));const style=getComputedStyle(document.querySelector('.case-preview-title'));const titleSize=parseFloat(style.fontSize),titleWeight=parseFloat(style.fontWeight);document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));
   return {terminalNotice,newerNotice,restored,titleSize,titleWeight,provenanceVisible};
  }finally{app.unmount();el.remove();Object.assign(libraryApi,oldLibrary);curriculumApi.knowledge=oldKnowledge;sessionStorage.removeItem(key);setActivePinia(prior)}
 });assert(result.terminalNotice);assert(result.newerNotice);assert.equal(result.restored,'已保存的案例标题');assert(result.titleSize>=22);assert(result.titleWeight>=600);assert(result.provenanceVisible);assert.deepEqual(browser.errors,[]);
 }finally{await browser.close()}
});


test('admin operation sections follow their URL and failed tasks use a business name',async()=>{
 const browser=await Browser.launch();try{
 await browser.goto(origin+'/#/login');await browser.wait('!!document.querySelector("#root").__vue_app__');
 const result=await browser.eval(async()=>{
  const {createApp,h,nextTick}=await import('/node_modules/.vite/deps/vue.js');
  const {createPinia,getActivePinia,setActivePinia}=await import('/node_modules/.vite/deps/pinia.js');
  const {createRouter,createMemoryHistory,RouterView}=await import((await (await fetch('/src/pages/Issues.vue')).text()).match(/from ["']([^"']*vue-router\.js[^"']*)/)[1]);
  const {TooltipProvider}=await import('/src/components/app/provider.js');const {default:Page}=await import('/src/pages/Issues.vue');
  const {useLearning}=await import('/src/store.js');const {api}=await import('/src/services/api.js');const {supportApi}=await import('/src/services/insights.js');const {modelApi}=await import('/src/services/models.js');
  const prior=getActivePinia(),pinia=createPinia(),store=useLearning(pinia),oldRequest=api.request,oldAccounts=api.accounts,oldSupport=supportApi.list,oldCapabilities=modelApi.capabilities,oldJobs=modelApi.list;
  store.user={id:'controlled-admin-sections',role:'admin'};
  api.accounts=async()=>[];supportApi.list=async()=>[];modelApi.capabilities=async()=>[];modelApi.list=async()=>[];
  api.request=async(path)=>path==='/health'?{}:path==='/ai/failures'?[{id:'controlled-failure',capability:'lesson_agent',createdAt:'2026-11-12T00:00:00Z',attemptNumber:1,retryCount:0,error:'受控任务失败',canRetry:false}]:[];
  const router=createRouter({history:createMemoryHistory(),routes:[{path:'/issues',component:Page}]});await router.push('/issues?section=accounts');await router.isReady();
  const el=document.createElement('div');document.body.append(el);const app=createApp({render:()=>h(TooltipProvider,null,{default:()=>h(RouterView)})});app.use(pinia);app.use(router);Object.assign(app._context.components,document.querySelector('#root').__vue_app__._context.components);app.mount(el);
  const wait=async(fn)=>{for(let i=0;i<200;i++){if(fn())return;await new Promise(r=>setTimeout(r,20))}throw Error('Admin section wait: '+el.textContent)};
  try{
   await wait(()=>el.textContent.includes('账号管理'));const directAccounts=!!el.querySelector('.account-manager');
   const queue=[...el.querySelectorAll('[role="tab"]')].find(b=>b.textContent.trim()==='问题反馈');queue.dispatchEvent(new MouseEvent('mousedown',{button:0,bubbles:true}));queue.click();await wait(()=>router.currentRoute.value.query.section==='queue');const changedUrl=el.textContent.includes('暂无问题反馈');
   await router.push('/issues?section=models');await wait(()=>el.textContent.includes('AI备课'));const failedName=el.querySelector('.analytics-queue strong')?.textContent;
   await router.push('/issues?section=accounts');await wait(()=>!!el.querySelector('.account-manager'));return {directAccounts,changedUrl,failedName,restoredAccounts:true,title:el.querySelector('h1')?.textContent};
  }finally{app.unmount();el.remove();api.request=oldRequest;api.accounts=oldAccounts;supportApi.list=oldSupport;modelApi.capabilities=oldCapabilities;modelApi.list=oldJobs;setActivePinia(prior)}
 });assert(result.directAccounts);assert(result.changedUrl);assert.equal(result.failedName,'AI备课');assert(result.restoredAccounts);assert.equal(result.title,'管理与运行');
 }finally{await browser.close()}
});
