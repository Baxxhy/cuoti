import { createRequire } from 'node:module'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import fs from 'node:fs'
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..')
process.env.PLAYWRIGHT_BROWSERS_PATH ||= path.join(root,'.runtime/playwright-browsers')
const require=createRequire(path.join(root,'frontend/package.json'))
const {chromium}=require('@playwright/test')
const browser=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH||undefined,args:['--no-sandbox']})
const base=process.env.SCZX_WEB_URL||'http://127.0.0.1:5176'
const page=await browser.newPage({viewport:{width:1280,height:900}})
const errors=[]
page.on('pageerror',e=>errors.push(e.message))
await page.route('**/api/v1/**',route=>{
 const url=new URL(route.request().url())
 if(url.pathname.endsWith('/dashboard'))return route.fulfill({json:{success:true,data:{grade:'初一'}}})
 if(url.pathname.endsWith('/auth/login'))return route.fulfill({status:401,json:{detail:'账号或密码不正确'}})
 return route.fulfill({status:401,json:{detail:'请先使用账号和密码登录'}})
})
try{
 await page.goto(base+'/#/pages/login/login')
 await page.getByRole('button',{name:'登录',exact:true}).waitFor()
 const fields=page.locator('input')
 await fields.nth(0).fill('student@example.com')
 await fields.nth(1).fill('wrong-password')
 await page.getByRole('button',{name:'登录',exact:true}).click()
 await page.getByText('账号或密码不正确',{exact:true}).first().waitFor()
 await page.goto(base+'/#/pages/register/register')
 await page.getByRole('button',{name:'创建账号',exact:true}).waitFor()
 await page.goto(base+'/#/pages/capture/capture')
 const input=page.locator('button.capture-zone')
 await input.waitFor()
 const chooser=page.waitForEvent('filechooser')
 await input.click()
 const file=await chooser
 await file.setFiles({name:'sample.png',mimeType:'image/png',buffer:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aVFEAAAAASUVORK5CYII=','base64')})
 await page.getByText('图片已选好',{exact:true}).waitFor()
 if(errors.length)throw new Error(errors.join('\n'))
 fs.mkdirSync(path.join(root,'.runtime'),{recursive:true})
 await page.screenshot({path:path.join(root,'.runtime/web-capture.png')})
 await page.getByLabel('手动录入错题',{exact:true}).click()
 await page.getByRole('button',{name:'保存并查看错题',exact:true}).waitFor()
 const hidden=await page.locator('.web-page-host').evaluateAll(nodes=>nodes.filter(node=>getComputedStyle(node).display==='none').map(node=>node.getBoundingClientRect().height))
 if(!hidden.length||hidden.some(height=>height!==0))throw Error('inactive cached pages occupied layout space')
 const active=await page.locator('.manual-page').boundingBox()
 if(!active||Math.abs(active.y)>1)throw Error('cached pages pushed the active page down')
 await page.goto(base+'/#/pages/not-a-real-page')
 const missing=page.getByRole('heading',{name:'页面不存在',exact:true});await missing.waitFor()
 const missingBox=await missing.boundingBox()
 if(!missingBox||missingBox.y>=900)throw Error('missing route fallback was pushed outside viewport')
 if(errors.length)throw new Error(errors.join('\n'))
 console.log('PASS: native Vue login validation, registration, image picker, cached-page layout and missing-route fallback; no page errors.')
}finally{await browser.close()}
