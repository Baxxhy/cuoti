const fs = require('node:fs'), path = require('node:path');
const root=path.resolve(__dirname,'../../../..');
const {chromium}=require(path.join(root,'frontend/node_modules/@playwright/test'));
(async()=>{
const browser=await chromium.launch({executablePath:path.join(root,'frontend/.playwright-browsers/chromium-1234/chrome-linux64/chrome'),args:['--no-sandbox'],env:{...process.env,LD_LIBRARY_PATH:path.join(root,'frontend/.playwright-libs/root/usr/lib/x86_64-linux-gnu')}});
try{
const page=await browser.newPage({viewport:{width:390,height:844},deviceScaleFactor:2});
const login=JSON.parse(fs.readFileSync(path.join(root,'.runtime/extended-curriculum/login.json'),'utf8'));
const res=await page.request.post('http://127.0.0.1:5174/api/v1/auth/login',{data:login});
if(res.status()!==200)throw Error('login unavailable');
const token=(await res.json()).data.access_token;
await page.addInitScript(t=>localStorage.setItem('minddimension_access_token',t),token);
const report=JSON.parse(fs.readFileSync(path.join(root,'.runtime/extended-curriculum/report.json'),'utf8'));
const id=report.cases.find(r=>r.key==='speed-units').question_id;
const out=path.join(__dirname,'../figures/screenshots');fs.mkdirSync(out,{recursive:true});
const shots=[['today','/pages/index/index'],['diagnosis',`/pages/diagnosis/diagnosis?id=${id}`],['repair',`/pages/repair/repair?id=${id}`],['map','/pages/error-map/error-map']];
const manifest=[];
for(const [name,route] of shots){await page.goto('http://127.0.0.1:5174/#'+route);await page.reload();await page.waitForTimeout(1800);await page.screenshot({path:path.join(out,name+'.png'),fullPage:true});const crop={today:[0,620],diagnosis:[230,510],repair:[630,570],map:[400,610]}[name];await page.screenshot({path:path.join(out,name+'-detail.png'),fullPage:true,clip:{x:0,y:crop[0],width:390,height:crop[1]}});manifest.push({file:name+'.png',route:route.split('?')[0],viewport:[390,844],scrollWidth:await page.evaluate(()=>document.documentElement.scrollWidth),date:'2026-10-18',source:'当前H5真实渲染，已有隔离核验账号，速度换算固定样例；只读取页面，未提交学习动作'});}
fs.writeFileSync(path.join(out,'provenance.json'),JSON.stringify(manifest,null,2));console.log('Captured '+manifest.length+' read-only actual H5 pages.');
}finally{await browser.close();}
})().catch(()=>{console.error('Read-only screenshot capture failed; no credentials printed');process.exitCode=1;});
