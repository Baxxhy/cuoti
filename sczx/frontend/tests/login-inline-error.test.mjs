import {test} from 'node:test';
import assert from 'node:assert/strict';
import {Browser,sleep} from './cdp.mjs';
const origin=process.env.SCZX_TEST_ORIGIN||'http://127.0.0.1:5175';
test('duplicate registration uses field error without a banner and clears after editing',async()=>{
 const b=await Browser.launch();try{
  await b.goto(origin+'/#/login');await b.wait('!!document.querySelector("#login-username")');
  await b.eval(()=>{const original=window.fetch;window.fetch=(url,opts)=>String(url).endsWith('/auth/register')?Promise.resolve(new Response(JSON.stringify({detail:'该账号或学号已注册，请直接登录。'}),{status:409,headers:{'Content-Type':'application/json'}})):original(url,opts);[...document.querySelectorAll('[role=tab]')].find(e=>e.textContent==='注册').click()});
  await b.wait('!!document.querySelector("#register-name")');await b.eval(()=>{for(const[id,value]of[['register-name','学生'],['login-username','existing-student'],['login-password','123456']]){const e=document.getElementById(id);e.value=value;e.dispatchEvent(new Event('input',{bubbles:true}))}});await sleep(100);await b.eval(()=>document.querySelector('.login-submit').click());
  await b.wait('!!document.querySelector(".el-form-item__error")');const r=await b.eval(()=>{const input=document.getElementById('login-username'),item=input.closest('.el-form-item');return{fieldError:item.querySelector('.el-form-item__error')?.textContent,banners:document.querySelectorAll('.login-card .el-alert').length,min:document.getElementById('login-password').minLength}});assert(r.fieldError.includes('已注册'));assert.equal(r.banners,0);assert.equal(r.min,6);
  await b.eval(()=>{const e=document.getElementById('login-username');e.value='another-student';e.dispatchEvent(new Event('input',{bubbles:true}))});await b.wait('!document.querySelector(".el-form-item__error")');assert.deepEqual(b.errors,[]);
 }finally{await b.close()}
});
