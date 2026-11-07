// Drive the real recognized question through confirmation/analysis/diagnosis.
// No routes or model responses are intercepted. Credentials arrive only on stdin.
import {createRequire} from 'node:module'
import {fileURLToPath} from 'node:url'
import path from 'node:path'
import fs from 'node:fs'
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..')
process.env.PLAYWRIGHT_BROWSERS_PATH ||= path.join(root,'.runtime/playwright-browsers')
const {chromium,expect}=createRequire(path.join(root,'frontend/package.json'))('@playwright/test')
const input=JSON.parse(fs.readFileSync(0,'utf8'))
const browser=await chromium.launch({args:['--no-sandbox']})
const context=await browser.newContext({viewport:{width:390,height:844},hasTouch:true,isMobile:true})
const page=await context.newPage(),errors=[],writes=[]
page.on('pageerror',error=>errors.push(error.message))
page.on('response',response=>{if(response.request().method()==='POST'&&/\/(confirm|analyze|diagnose)$/.test(new URL(response.url()).pathname))writes.push({operation:new URL(response.url()).pathname.split('/').at(-1),status:response.status()})})
await page.addInitScript(token=>localStorage.setItem('minddimension_access_token',JSON.stringify(token)),input.token)
try{
 await page.goto(input.base+'/#/pages/ocr/ocr?id='+input.question_id)
 await expect(page.getByText('暂未发现你的作答',{exact:true})).toBeVisible()
 await expect(page.getByRole('button',{name:'确认并分析',exact:true})).toBeVisible()
 await page.screenshot({path:path.join(input.artifacts,'live-model-before-confirmation.png'),fullPage:true})
 await page.getByRole('button',{name:'修改内容',exact:true}).click()
 const question=await page.locator('.question-editor textarea').inputValue()
 if(!question.replace(/[\s$\\{}]/g,'').includes('2x+3=11'))throw Error('recognized equation not displayed correctly')
 await page.locator('.meta-row .web-picker').nth(1).click()
 await page.locator('.web-selector-content .web-selector-item').filter({hasText:/^初一$/}).click()
 await page.locator('.web-selector-action.confirm').click()
 await page.locator('.content-section').filter({has:page.getByText('我当时的答案',{exact:true})}).locator('textarea').fill('x=7')
 for(const [index,text] of ['2x=14','x=7'].entries()){
  await page.getByRole('button',{name:'添加解题步骤',exact:true}).click()
  await page.locator('.step-editor textarea').nth(index).fill(text)
 }
 await page.getByRole('button',{name:'确认并分析',exact:true}).click()
 await page.waitForURL('**/#/pages/diagnosis/diagnosis?id='+input.question_id,{timeout:240000})
 await expect(page.getByRole('button',{name:'开始订正',exact:true})).toBeVisible()
 await page.getByText('我的解题过程',{exact:true}).click()
 await expect(page.locator('.step-row.first')).toContainText('14')
 await expect(page.locator('.first-tag')).toHaveText('从这里开始')
 await page.screenshot({path:path.join(input.artifacts,'live-model-diagnosis.png'),fullPage:true})
 const api=input.base+'/api/v1/questions/'+input.question_id
 const headers={Authorization:'Bearer '+input.token}
 const before=(await (await page.request.get(api,{headers})).json()).data
 await page.reload()
 await expect(page.getByRole('button',{name:'开始订正',exact:true})).toBeVisible()
 const after=(await (await page.request.get(api,{headers})).json()).data
 if(before.diagnosis.id!==after.diagnosis.id||after.diagnosis.first_error_step!==0)throw Error('diagnosis did not survive reload')
 if(writes.length!==3||writes.map(row=>row.operation).join(',')!=='confirm,analyze,diagnose'||writes.some(row=>row.status!==200))throw Error('confirmation/analysis/diagnosis requests differed from expected real sequence')
 if(errors.length)throw Error('browser page errors: '+errors.join(';'))
 fs.writeFileSync(path.join(input.artifacts,'live-model-browser.json'),JSON.stringify({success:true,requestMocks:false,writes,errors,firstErrorStep:after.diagnosis.first_error_step,reloadPreservedDiagnosis:true},null,2)+'\n')
 console.log('PASS: real model result displayed, student steps confirmed, diagnosis and reload verified in browser.')
}finally{await browser.close()}
