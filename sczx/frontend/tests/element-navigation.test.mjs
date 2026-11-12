import{test}from'node:test';import assert from'node:assert/strict';import{Browser}from'./cdp.mjs';
test('Element menu and tabs support keyboard selection, recover rejected navigation and have no text-side accent',async()=>{
 const b=await Browser.launch();try{
 await b.goto((process.env.SCZX_TEST_ORIGIN||'http://127.0.0.1:5177')+'/#/login');await b.wait("!!document.querySelector('#root')?.__vue_app__");
 const result=await b.eval(async()=>{
  const{createApp,h,ref}=await import('/node_modules/.vite/deps/vue.js'),{createPinia,getActivePinia,setActivePinia}=await import('/node_modules/.vite/deps/pinia.js');
  const source=await(await fetch('/src/components/SidebarContent.vue')).text();const{createRouter,createMemoryHistory}=await import(source.match(/from ["']([^"']*vue-router\.js[^"']*)/)[1]);
  const{default:Sidebar}=await import('/src/components/SidebarContent.vue'),{default:Tabs}=await import('/src/components/WorkspaceNavigation.vue'),{useLearning}=await import('/src/store.js');
  const prior=getActivePinia(),pinia=createPinia(),store=useLearning(pinia);store.user={id:'navigation-check',role:'student',displayName:'导航验收'};store.status='ready';
  const blocked=ref(false),router=createRouter({history:createMemoryHistory(),routes:['home','wrong','memory','class'].map(name=>({path:'/'+name,name,component:{render:()=>h('div')}}))});router.beforeEach(()=>!blocked.value);await router.push('/home');await router.isReady();
  const el=document.createElement('div');document.body.append(el);const app=createApp({render:()=>h('section',[h(Sidebar),h(Tabs)])});app.use(pinia);app.use(router);app.provide('shell',{openHelp(){},logout(){}});Object.assign(app._context.components,document.querySelector('#root').__vue_app__._context.components);app.mount(el);
  const wait=async fn=>{for(let i=0;i<100;i++){if(fn())return;await new Promise(r=>setTimeout(r,20))}throw Error('Navigation did not settle')};
  try{
   const items=el.querySelectorAll('.el-menu-item');items[1].focus();items[1].dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',code:'Enter',bubbles:true}));await wait(()=>router.currentRoute.value.name==='wrong');
   [...el.querySelectorAll('[role=tab]')].find(n=>n.textContent==='复习建议').click();await wait(()=>router.currentRoute.value.name==='memory');
   blocked.value=true;[...el.querySelectorAll('[role=tab]')].find(n=>n.textContent==='错题本').click();await new Promise(r=>setTimeout(r,30));await wait(()=>el.querySelector('[role=tab].is-active')?.textContent==='复习建议');
   items[2].focus();items[2].dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',code:'Enter',bubbles:true}));await new Promise(r=>setTimeout(r,30));await wait(()=>el.querySelector('.el-menu-item.is-active')?.textContent==='错题与复习');
   const selected=[...el.querySelectorAll('.el-menu-item.is-active,.workspace-main-nav [aria-current=page]')];
   return{route:router.currentRoute.value.name,selectedTab:el.querySelector('[role=tab].is-active').textContent,noAccent:selected.every(n=>getComputedStyle(n).boxShadow==='none'&&parseFloat(getComputedStyle(n).borderLeftWidth)===0),officialIcons:el.querySelectorAll('.el-icon>svg').length>0,lucideIcons:el.querySelectorAll('[class*=lucide]').length};
  }finally{app.unmount();el.remove();setActivePinia(prior)}
 });assert.deepEqual(result,{route:'memory',selectedTab:'复习建议',noAccent:true,officialIcons:true,lucideIcons:0});assert.deepEqual(b.errors,[]);
 }finally{await b.close()}
});
