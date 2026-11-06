// Reproduce the original browser acceptance canvas so the fixture admits only it.
import {createRequire} from 'node:module'
import {fileURLToPath} from 'node:url'
import path from 'node:path'
import fs from 'node:fs'
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..')
process.env.PLAYWRIGHT_BROWSERS_PATH ||= path.join(root,'.runtime/playwright-browsers')
const {chromium,devices}=createRequire(path.join(root,'frontend/package.json'))('@playwright/test')
const browser=await chromium.launch({args:['--no-sandbox']})
try {
 const context=await browser.newContext({...devices['Pixel 7'],viewport:{width:390,height:844}})
 const page=await context.newPage()
 const raw=await page.evaluate(()=>{
  const canvas=document.createElement('canvas');canvas.width=120;canvas.height=60
  const context=canvas.getContext('2d');context.fillStyle='red';context.fillRect(0,0,120,60)
  context.fillStyle='black';context.font='20px sans-serif';context.fillText('x=4',10,35)
  return canvas.toDataURL('image/png').split(',')[1]
 })
 fs.writeFileSync(process.argv[2],Buffer.from(raw,'base64'))
} finally {await browser.close()}
