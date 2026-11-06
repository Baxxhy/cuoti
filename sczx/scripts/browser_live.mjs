import {createRequire} from 'node:module'
import {fileURLToPath} from 'node:url'
import path from 'node:path'
import fs from 'node:fs'
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..')
process.env.PLAYWRIGHT_BROWSERS_PATH ||= path.join(root,'.runtime/playwright-browsers')
const {chromium}=createRequire(path.join(root,'frontend/package.json'))('@playwright/test')
const input=JSON.parse(fs.readFileSync(0,'utf8'))
const browser=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH||undefined,args:['--no-sandbox']})
const page=await browser.newPage({viewport:{width:1280,height:900}})
const errors=[]
page.on('pageerror',e=>errors.push(e.message))
await page.addInitScript(token=>localStorage.setItem('minddimension_access_token',JSON.stringify(token)),input.token)
const endpoint=input.base+'/api/v1/learning-tasks/'+input.task_id
async function current(){const r=await page.request.get(endpoint,{headers:{Authorization:'Bearer '+input.token}});if(!r.ok())throw Error('task read '+r.status());return (await r.json()).data}
async function waitAfter(version){
 for(let i=0;i<150;i++){
  const task=await current()
  if(task.version>version&&['waiting_student','completed'].includes(task.status))return task
  if(['failed','stale','cancelled'].includes(task.status))throw Error('task stopped: '+task.status+' '+task.exit_reason)
  await new Promise(resolve=>setTimeout(resolve,200))
 }
 throw Error('task progress timeout')
}
try{
 await page.goto(input.base+'/#/pages/task/task?id='+input.task_id)
 let task=await waitAfter(0)
 for(const answer of ['11-3','x=4','x=7']){
  await page.reload()
  const field=page.getByPlaceholder('输入答案或解题步骤',{exact:true})
  await field.waitFor({state:'visible'})
  await field.fill(answer)
  const response=page.waitForResponse(r=>r.url().endsWith('/actions')&&r.request().method()==='POST')
  await page.getByRole('button',{name:'提交作答',exact:true}).click()
  const submitted=await response
  if(submitted.status()!==202)throw Error('answer rejected: '+submitted.status())
  task=await waitAfter(task.version)
 }
 if(task.status!=='completed'||task.learning_applied!==true)throw Error('learning did not complete independently')
 await page.reload()
 await page.getByText('自检要点',{exact:false}).first().waitFor({state:'visible'})
 if(errors.length)throw Error(errors.join('\n'))
 await page.screenshot({path:path.join(input.artifacts,'task-complete.png'),fullPage:true})
 console.log('PASS: real browser task repair, original answer, contrast and refresh recovery; no request mocks or page errors.')
}finally{await browser.close()}
