import {test} from 'node:test';
import assert from 'node:assert/strict';
import {Browser} from './cdp.mjs';
test('memory return controls preserve original learning task and knowledge route',async()=>{
 const b=await Browser.launch();try{await b.goto((process.env.SCZX_TEST_ORIGIN||'http://127.0.0.1:5177')+'/#/login');const result=await b.eval(async()=>{
 const {createApp,h,nextTick}=await import('/node_modules/.vite/deps/vue.js');const source=await(await fetch('/src/pages/Classroom.vue')).text();const {createRouter,createMemoryHistory}=await import(source.match(/from ["']([^"']*vue-router\.js[^"']*)/)[1]);const {default:Return}=await import('/src/components/MemoryReturn.vue');const router=createRouter({history:createMemoryHistory(),routes:[{path:'/repair',component:Return}]});await router.push('/repair?returnTask=task-B&returnKnowledge=kp-A');await router.isReady();const el=document.createElement('div');document.body.append(el);const app=createApp({render:()=>h(Return)});app.use(router);Object.assign(app._context.components,document.querySelector('#root').__vue_app__._context.components);app.mount(el);
 try{await nextTick();[...el.querySelectorAll('button')].find(e=>e.textContent.includes('查看复习后的证据')).click();await new Promise(r=>setTimeout(r,100));return {hash:location.hash}}finally{app.unmount();el.remove()}
 });const destination=result.hash.startsWith('#/login?')?new URLSearchParams(result.hash.slice(result.hash.indexOf('?')+1)).get('next'):result.hash.slice(1);assert.equal(destination,'/memory?knowledge=kp-A&returnTask=task-B');assert.deepEqual(b.errors,[])}finally{await b.close()}
});
test('late memory response cannot overwrite a different task suggestion',async()=>{
 const b=await Browser.launch();try{await b.goto((process.env.SCZX_TEST_ORIGIN||'http://127.0.0.1:5177')+'/#/login');const result=await b.eval(async()=>{
 const {createApp,h,ref,nextTick}=await import('/node_modules/.vite/deps/vue.js');const {default:Bridge}=await import('/src/components/MemoryBridge.vue');const original=fetch;let release,count=0;const task=ref({id:'A',snapshot:{knowledgeIds:['kpA']}});const data=(id)=>({items:[{id:'kp'+id,name:'知识'+id}],recommendations:[{id:'r'+id,knowledgeId:'kp'+id,label:'检查'+id,reason:'来源'+id,target:'/check?task='+id}]});window.fetch=(url,opts)=>String(url)==='/api/memory'?(++count===1?new Promise(r=>release=()=>r(new Response(JSON.stringify(data('A'))))):Promise.resolve(new Response(JSON.stringify(data('B'))))):original(url,opts);
 const el=document.createElement('div');document.body.append(el);const app=createApp({render:()=>h(Bridge,{task:task.value})});Object.assign(app._context.components,document.querySelector('#root').__vue_app__._context.components);app.mount(el);
 try{await new Promise(r=>setTimeout(r,50));task.value={id:'B',snapshot:{knowledgeIds:['kpB']}};await nextTick();await new Promise(r=>setTimeout(r,80));release();await new Promise(r=>setTimeout(r,80));return el.textContent}finally{app.unmount();el.remove();window.fetch=original}
 });assert.ok(result.includes('知识B'));assert.ok(!result.includes('知识A'));assert.deepEqual(b.errors,[])}finally{await b.close()}
});
