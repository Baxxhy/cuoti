import{test}from'node:test';import assert from'node:assert/strict';import{Browser}from'./cdp.mjs';
test('published legacy candidate explanation renders actual line breaks without changing the original answer',async()=>{
 const b=await Browser.launch();try{
  await b.goto((process.env.SCZX_TEST_ORIGIN||'http://127.0.0.1:5177')+'/#/login');await b.wait("!!document.querySelector('#root')?.__vue_app__");
  const result=await b.eval(async()=>{
   const{createApp,h}=await import('/node_modules/.vite/deps/vue.js'),{createPinia,getActivePinia,setActivePinia}=await import('/node_modules/.vite/deps/pinia.js');
   const src=await(await fetch('/src/main.js')).text(),{createRouter,createMemoryHistory}=await import(src.match(/from ["']([^"']*vue-router\.js[^"']*)/)[1]);
   const{useLearning}=await import('/src/store.js'),{TooltipProvider}=await import('/src/components/app/provider.js'),{default:Page}=await import('/src/pages/Examinations.vue');
   const oldPinia=getActivePinia(),pinia=createPinia(),store=useLearning(pinia),original=fetch;
   store.user={id:'student-feedback',role:'student'};store.status='ready';store.data.classrooms=[];store.data.tasks=[];
   const exam={id:'old-feedback',title:'已公布的原试卷',resultsAt:'2026-11-12T00:00:00Z',paper:{total:10,entries:[{versionId:'q1',points:10,question:{kind:'calculation',prompt:'解方程',equation:'x+5=12',answer:'7',source:'AI候选，待教师审核；ModelJob old-job',explanation:'两边减5。\\\\n\\\\n1. 得x=7。\\\\n本题为待教师审核的候选题。'}}]},submission:{id:'sub',startedAt:'2026-11-12T00:00:00Z',submittedAt:'2026-11-12T00:01:00Z',revision:2,answers:{q1:{answer:'8',reason:'原错误解释'}},grades:{q1:{score:0,comment:'两边应同减5'}},automatic:{},total:0}};
   window.fetch=(u,o)=>String(u).startsWith('/api/')?Promise.resolve(new Response(JSON.stringify(String(u)==='/api/exams/old-feedback'?exam:[]),{headers:{'Content-Type':'application/json'}})):original(u,o);
   const router=createRouter({history:createMemoryHistory(),routes:[{path:'/exams',component:Page}]});await router.push('/exams?exam=old-feedback');await router.isReady();
   const el=document.createElement('div');document.body.append(el);const app=createApp({render:()=>h(TooltipProvider,null,{default:()=>h(Page)})});app.use(pinia);app.use(router);app.provide('notify',()=>{});Object.assign(app._context.components,document.querySelector('#root').__vue_app__._context.components);app.mount(el);
   try{for(let i=0;i<100&&!el.querySelector('.exam-result-grade');i++)await new Promise(r=>setTimeout(r,20));return{text:el.querySelector('.exam-result-grade')?.innerText,answer:el.querySelector('input')?.value,readonly:el.querySelector('input')?.readOnly,unchanged:exam.submission.answers.q1.answer==='8'&&exam.paper.entries[0].question.explanation.includes('\\\\n')}}finally{app.unmount();el.remove();window.fetch=original;setActivePinia(oldPinia)}
  });assert(result.text.includes('两边减5。\n\n1. 得x=7。'));assert(!result.text.includes('\\n'));assert(!result.text.includes('待教师审核'));assert.equal(result.answer,'8');assert(result.readonly);assert(result.unchanged);assert.deepEqual(b.errors,[]);
 }finally{await b.close()}
});
