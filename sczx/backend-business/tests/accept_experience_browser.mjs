import{readFile,writeFile}from'node:fs/promises';
import{Browser}from'../../frontend/tests/cdp.mjs';
const p=JSON.parse(await readFile(process.env.SCZX_INNOVATION_PRIVATE||'/tmp/sczx-innovation-real-login.json','utf8'));
const evidence=JSON.parse(await readFile(process.env.SCZX_INNOVATION_CHAIN||new URL('../../docs/verification/innovation_20261114_v1/real-guidance-chain.json',import.meta.url),'utf8'));
const out=[];const dir=new URL('../../docs/verification/innovation_20261114_v1/',import.meta.url).pathname;
for(const role of ['a','t1','s0']){
 const b=await Browser.launch();try{
 await b.viewport(1440,1000);await b.send('Page.addScriptToEvaluateOnNewDocument',{source:`{const original=window.fetch;window.fetch=(url,options)=>original(typeof url==='string'&&url.startsWith('/api')?'http://127.0.0.1:8104'+url:url,options);}`});
 await b.goto('http://127.0.0.1:5175/#/login');await b.wait('!!document.querySelector("#login-username")');
 await b.eval(({username,password})=>{for(const[id,value]of [['login-username',username],['login-password',password]]){const el=document.getElementById(id);el.value=value;el.dispatchEvent(new Event('input',{bubbles:true}))}document.querySelector('.auth-form-panel form').requestSubmit()},{username:p.prefix+role,password:p.password});
 await b.wait('!location.hash.includes("/login")',15000);
 if(role==='a'){
 await b.goto('http://127.0.0.1:5175/#/manage?case='+p.case);await b.wait('!!document.querySelector(".library-editor")');
 await b.eval(()=>[...document.querySelectorAll('.library-editor button')].find(x=>x.textContent.trim()==='创建修订')?.click());
 await b.wait('!!document.querySelector(".library-editor fieldset")');
 await b.eval(()=>[...document.querySelectorAll('.library-editor [role=tab]')].find(x=>x.textContent.includes('出处')).click());
 await b.wait('document.body.textContent.includes("来源类型")');
 out.push({role:'admin',sourceTypeVisible:await b.eval(()=>document.querySelector('.library-editor').textContent.includes('团队自编')),authorizationFields:await b.eval(()=>document.querySelector('.library-editor').textContent.includes('授权依据')),url:await b.eval(()=>location.hash)});
 }else if(role==='t1'){
 await b.goto('http://127.0.0.1:5175/#/agent?lesson='+p.lesson+'&job='+p.teacherJob);await b.wait('!!document.querySelector("#agent-goal")');
 await b.eval(()=>[...document.querySelectorAll('[role=tab]')].find(x=>x.textContent.includes('依据与核验')).click());
 await b.wait('document.body.textContent.includes("教法选择依据")');out.push({role:'teacher',methodVisible:await b.eval(()=>document.querySelector('.planning-evidence').textContent.includes('先列两组相等数量')),sourceLinks:await b.eval(()=>document.querySelectorAll('.planning-evidence a').length),url:await b.eval(()=>location.hash)});
 }else{
 await b.goto('http://127.0.0.1:5175/#/learn?task='+p.task);await b.wait('!!document.querySelector(".lesson-desktop-outline")');
 const blockTitle=evidence.studentJob.input.context.block.title;
 await b.eval(title=>{const el=[...document.querySelectorAll('.lesson-desktop-outline .el-menu-item')].find(x=>x.textContent.includes(title));if(!el)throw Error('Missing practice outline: '+title);el.click()},blockTitle);
 await b.wait('!!document.querySelector(".curriculum-answer")');
 await b.eval(()=>[...document.querySelectorAll('button')].find(x=>x.textContent.trim()==='问一问').click());
 await b.wait('document.body.textContent.includes("本轮指导依据")');
 await b.eval(()=>[...document.querySelectorAll('.el-collapse-item__header')].find(x=>x.textContent.includes('本轮指导依据')).click());
 out.push({role:'student',realHintVisible:await b.eval(hint=>document.body.textContent.includes(hint),evidence.studentJob.result.hint),decisionVisible:await b.eval(()=>document.body.textContent.includes('采用教法：')),url:await b.eval(()=>location.hash)});
 }
 await b.eval(()=>document.fonts.ready);await b.eval(()=>new Promise(r=>setTimeout(r,450)));
 await b.screenshot(dir+({a:'admin-source',t1:'teacher-decision',s0:'student-guidance'}[role])+'.png');out.at(-1).errors=b.errors;
 }catch(error){out.push({role,error:error.message,errors:b.errors,body:await b.eval(()=>document.body.textContent.slice(-3500))});await b.screenshot(dir+'failure-'+role+'.png');}finally{await b.close()}
}
await writeFile(dir+'browser-real.json',JSON.stringify(out,null,2));console.log(JSON.stringify(out));
