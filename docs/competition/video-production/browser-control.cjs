const {createRequire}=require('module');const path=require('path');const fs=require('fs');const readline=require('readline');
process.env.PLAYWRIGHT_BROWSERS_PATH=path.resolve('frontend/.playwright-browsers');
const req=createRequire(path.resolve('frontend/package.json'));const {chromium}=req('@playwright/test');
(async()=>{
 global.browser=await chromium.launch({headless:true,executablePath:path.resolve('frontend/.playwright-browsers/chromium-1234/chrome-linux64/chrome'),args:['--no-sandbox'],env:{...process.env,LD_LIBRARY_PATH:path.resolve('frontend/.playwright-libs/root/usr/lib/x86_64-linux-gnu')+':'+(process.env.LD_LIBRARY_PATH||'')}});
 global.ctx=await browser.newContext({viewport:{width:432,height:936},deviceScaleFactor:2,isMobile:true,hasTouch:true,acceptDownloads:true});
 global.page=await ctx.newPage();global.base='http://127.0.0.1:5175';global.w=ms=>page.waitForTimeout(ms);global.dump=async()=>({url:page.url(),body:(await page.locator('body').innerText()).slice(0,18000),inputs:await page.locator('input,textarea,select').evaluateAll(es=>es.map(x=>({tag:x.tagName,id:x.id,ph:x.placeholder,label:x.getAttribute('aria-label')})))});
 global.go=async p=>{await page.goto(base+'/#/pages/'+p);await w(1500);return await dump()};global.shot=async n=>{await page.screenshot({path:path.resolve('.runtime/video-'+n+'.png')});return 'screenshot '+n};
 global.click=async t=>{await page.getByRole('button',{name:t,exact:true}).click();await w(1200);return await dump()};
 console.log('READY');const rl=readline.createInterface({input:process.stdin});
 for await (const code of rl){try{const result=await (new Function('return (async()=>{'+code+'})()'))();console.log(JSON.stringify(result??'OK'));}catch(e){console.log('ERROR '+e.message)}}
 await browser.close();
})();
