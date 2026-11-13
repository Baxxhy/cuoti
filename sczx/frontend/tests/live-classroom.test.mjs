import {test} from 'node:test';
import assert from 'node:assert/strict';
import {Browser} from './cdp.mjs';

test('classroom polling preserves unsaved input, recovers errors and ignores old-room responses', async () => {
  const b = await Browser.launch();
  try {
    await b.goto((process.env.SCZX_TEST_ORIGIN || 'http://127.0.0.1:5175') + '/#/login');
    const result = await b.eval(async () => {
      const {createApp, h, nextTick} = await import('/node_modules/.vite/deps/vue.js');
      const {createPinia, getActivePinia, setActivePinia} = await import('/node_modules/.vite/deps/pinia.js');
      const source = await (await fetch('/src/pages/LiveClassroom.vue')).text();
      const routerUrl = source.match(/from\s*["']([^"']*vue-router[^"']*)["']/)[1];
      const {createRouter, createMemoryHistory, RouterView} = await import(routerUrl);
      const {TooltipProvider} = await import('/src/components/app/provider.js');
      const {default: Page} = await import('/src/pages/LiveClassroom.vue');
      const {useLearning} = await import('/src/store.js');
      const previousPinia = getActivePinia(), pinia = createPinia();
      useLearning(pinia).user = {id: 'student', role: 'student'};
      const fixture = id => ({id, title: id === 'a' ? '课堂甲' : '课堂乙', status: 'active', joined: true, currentId: id, activities: [{id, position: 1, question: {prompt: '解方程', equation: 'x+2=9'}, answer: {answer: id === 'a' ? '7' : '9', reason: '共同运算', revision: 1}}]});
      const originalFetch = window.fetch;
      let fail = false, delay = false, release;
      window.fetch = (url, options) => {
        if (!String(url).includes('/api/')) return originalFetch(url, options);
        if (String(url).endsWith('/live/a') && delay) return new Promise(resolve => {release = () => resolve(new Response(JSON.stringify(fixture('a'))));});
        const data = fail ? {detail: '网络中断，请重试'} : String(url).includes('/live/') ? fixture(String(url).split('/').at(-1)) : String(url).includes('courses') ? [] : [];
        return Promise.resolve(new Response(JSON.stringify(data), {status: fail ? 503 : 200}));
      };
      const el = document.createElement('div'); document.body.append(el);
      const router = createRouter({history: createMemoryHistory(), routes: [{path: '/live', component: Page}]});
      const app = createApp({render: () => h(TooltipProvider, null, {default: () => h(RouterView)})});
      Object.assign(app._context.components, document.querySelector('#root').__vue_app__._context.components);
      app.use(pinia); app.use(router); await router.push('/live?session=a'); app.mount(el);
      const wait = async predicate => {for (let i=0; i<100; i++) {if (predicate()) return; await new Promise(r=>setTimeout(r,20));} throw Error('Classroom condition timed out');};
      const refresh = () => el.querySelector('[aria-label="刷新课堂"]').click();
      try {
        await wait(() => el.querySelector('input')?.value === '7');
        const input = el.querySelector('input'); input.value='11'; input.dispatchEvent(new Event('input', {bubbles:true})); await nextTick();
        refresh(); await new Promise(r=>setTimeout(r,80)); const unsaved=input.value;
        fail=true; refresh(); await wait(()=>el.textContent.includes('网络中断')); const offline=input.value;
        fail=false; refresh(); await wait(()=>!el.textContent.includes('网络中断'));
        delay=true; refresh(); await wait(()=>!!release);
        await router.push('/live?session=b'); release(); await new Promise(r=>setTimeout(r,80));
        const oldResponseIgnored=!el.textContent.includes('课堂甲') && !el.querySelector('input');
        delay=false; refresh(); await wait(()=>el.querySelector('input')?.value==='9');
        return {unsaved, offline, oldResponseIgnored, newRoom:el.textContent.includes('课堂乙'), value:el.querySelector('input').value};
      } finally {window.fetch=originalFetch; app.unmount(); el.remove(); setActivePinia(previousPinia);}
    });
    assert.deepEqual(result, {unsaved:'11', offline:'11', oldResponseIgnored:true, newRoom:true, value:'9'});
    assert.deepEqual(b.errors, []);
  } finally {await b.close();}
});
