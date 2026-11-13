import {test} from 'node:test';
import assert from 'node:assert/strict';
import {Browser} from './cdp.mjs';
test('reviewed experience provenance and student decision remain readable in official disclosure controls',async()=>{
 const b=await Browser.launch();try{
 await b.goto((process.env.SCZX_TEST_ORIGIN||'http://127.0.0.1:5175')+'/#/login');await b.wait('!!document.querySelector("#root")?.__vue_app__');
 const value=await b.eval(async()=>{
 const {createApp,h,ref,nextTick}=await import('/node_modules/.vite/deps/vue.js');const {TooltipProvider}=await import('/src/components/app/provider.js');const {default:Result}=await import('/src/components/ModelResult.vue');const {default:Article}=await import('/src/components/CaseArticle.vue');
 const selected={versionId:'version-engineering',reason:'学科与年级符合；当前自述提到文本证据',method:'先划原句，再说明它支持哪一个观点'};
 const decision=ref({selected:[selected],fallback:false,notice:'参考团队自编并已审核的教学经验'});
 const el=document.createElement('div');document.body.append(el);const app=createApp({render:()=>h(TooltipProvider,null,{default:()=>[h(Result,{job:{id:'job-engineering',capability:'text',status:'succeeded',result:{title:'先找原句',hint:'请划出支持观点的原句',steps:['说明原句与观点的关系'],question:'哪一句最直接？',experienceDecision:decision.value,difficultyAssessment:{reason:'现有证据不足以判断困难原因'},sources:[]}}}),h(Article,{value:{title:'自编阅读案例',content:'依据原句说明观点',provenance:{kind:'team',author:'本地团队夹具'},experience:{diagnosis:'指出原文依据',strategy:selected.method,effectCheck:'换一段材料独立解释'},references:[]}})]})});
 Object.assign(app._context.components,document.querySelector('#root').__vue_app__._context.components);app.mount(el);
 try{await nextTick();const trigger=[...el.querySelectorAll('.el-collapse-item__header')].find(e=>e.textContent.includes('本轮指导依据'));if(!trigger)throw Error('Missing decision disclosure');trigger.click();await nextTick();const selectedText=el.querySelector('.model-run-history').textContent;const sourceLabel=el.querySelector('.case-reading-article .el-tag')?.textContent;const methodInArticle=el.querySelector('.case-reading-article').textContent.includes(selected.method);
 decision.value={selected:[],fallback:true,notice:'当前没有匹配到经过审核的经验，使用通用AI指导'};await nextTick();return {selectedText,sourceLabel,methodInArticle,authorVisible:el.querySelector('.case-meta').textContent.includes('本地团队夹具'),fallbackText:el.querySelector('.model-run-history').textContent,official:!!el.querySelector('.el-collapse'),body:el.textContent};}finally{app.unmount();el.remove()}
 });assert(value.selectedText.includes('文本证据'));assert(value.selectedText.includes('先划原句'));assert.equal(value.sourceLabel,'团队自编');assert(value.methodInArticle);assert(value.authorVisible);assert(value.fallbackText.includes('通用AI指导'));assert(!value.fallbackText.includes('先划原句'));assert(!value.body.includes('version-engineering'));assert(value.official);assert.deepEqual(b.errors,[]);
 }finally{await b.close()}
});
