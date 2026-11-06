import { createRequire } from 'node:module'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import fs from 'node:fs'
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..')
const require=createRequire(path.join(root,'frontend/package.json'))
const {chromium}=require('@playwright/test')
const browser=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH||path.join(root,'frontend/.playwright-browsers/chromium-1234/chrome-linux64/chrome'),args:['--no-sandbox'],env:{...process.env,LD_LIBRARY_PATH:path.join(root,'frontend/.playwright-libs/root/usr/lib/x86_64-linux-gnu')+':'+(process.env.LD_LIBRARY_PATH||'')}})
const page=await browser.newPage({viewport:{width:1280,height:900}})
const errors=[]
page.on('pageerror',e=>errors.push(e.message))
await page.route('**/api/v1/**',route=>{
 const url=new URL(route.request().url())
 if(url.pathname.endsWith('/auth/login'))return route.fulfill({status:401,json:{detail:'账号或密码不正确'}})
 return route.fulfill({status:401,json:{detail:'请先使用账号和密码登录'}})
})
try{
 await page.goto('http://127.0.0.1:5176/#/pages/login/login')
 await page.getByRole('button',{name:'登录',exact:true}).waitFor()
 const fields=page.locator('input')
 await fields.nth(0).fill('student@example.com')
 await fields.nth(1).fill('wrong-password')
 await page.getByRole('button',{name:'登录',exact:true}).click()
 await page.getByText('账号或密码不正确',{exact:true}).first().waitFor()
 await page.goto('http://127.0.0.1:5176/#/pages/register/register')
 await page.getByRole('button',{name:'创建账号',exact:true}).waitFor()
 await page.goto('http://127.0.0.1:5176/#/pages/capture/capture')
 const input=page.locator('button.capture-zone')
 await input.waitFor()
 const chooser=page.waitForEvent('filechooser')
 await input.click()
 const file=await chooser
 await file.setFiles({name:'sample.png',mimeType:'image/png',buffer:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aVFEAAAAASUVORK5CYII=','base64')})
 await page.getByText('图片已选好',{exact:true}).waitFor()
 if(errors.length)throw new Error(errors.join('\n'))
 fs.mkdirSync(path.join(root,'sczx/.runtime'),{recursive:true})
 await page.screenshot({path:path.join(root,'sczx/.runtime/web-capture.png')})
 console.log('PASS: native Vue login validation, registration screen and browser image picker; no page errors.')
}finally{await browser.close()}
