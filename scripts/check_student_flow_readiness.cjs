// Actual-model diagnosis and learning, using only public questions to solve.
const fs = require('node:fs')
const path = require('node:path')
const { execFileSync } = require('node:child_process')
const root = path.resolve(__dirname, '..')
const { chromium, expect } = require(path.join(root, 'frontend/node_modules/@playwright/test'))
async function main() {
  const actor = JSON.parse(fs.readFileSync(path.join(root,'.runtime/student-personas-accounts.json'),'utf8')).find(x=>x.name==='甲')
  const output = path.join(root,'docs/reviews/2026-10-student-flow-readiness/screenshots')
  fs.mkdirSync(output,{recursive:true})
  const browser = await chromium.launch({executablePath:path.join(root,'frontend/.playwright-browsers/chromium-1234/chrome-linux64/chrome'),args:['--no-sandbox'],env:{...process.env,LD_LIBRARY_PATH:path.join(root,'frontend/.playwright-libs/root/usr/lib/x86_64-linux-gnu')}})
  const report={kind:'actual-model-student-flow',student_trial:false,passed:false}
  try {
    const page=await browser.newPage({viewport:{width:375,height:812}})
    const errors=[]
    page.on('pageerror',()=>errors.push('pageerror'))
    const login=await page.request.post('http://127.0.0.1:8002/api/v1/auth/login',{data:{email:actor.email,password:actor.password}})
    expect(login.ok()).toBeTruthy()
    const token=(await login.json()).data.access_token
    await page.addInitScript(value=>localStorage.setItem('minddimension_access_token',value),token)
    for(const width of [375,1280]) {
      await page.setViewportSize({width,height:900})
      await page.goto('http://127.0.0.1:5175/#/pages/diagnosis/diagnosis?id='+actor.question_id)
      await page.reload()
      await expect(page.getByRole('button',{name:'开始订正',exact:true})).toBeVisible({timeout:30000})
      await expect(page.locator('.student-thought')).toContainText('3x=17+2')
      expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
      await page.screenshot({path:path.join(output,'diagnosis-'+width+'.png'),fullPage:true})
    }
    await page.setViewportSize({width:375,height:812})
    await page.getByRole('button',{name:'开始订正',exact:true}).click()
    await expect(page.getByText('先订正这一步',{exact:true})).toBeVisible({timeout:30000})
    await page.locator('.answer-input textarea,textarea.answer-input').fill('3x=15')
    await page.screenshot({path:path.join(output,'repair.png'),fullPage:true})
    await page.getByRole('button',{name:'提交作答',exact:true}).click()
    await expect(page.getByText('重新作答',{exact:true})).toBeVisible({timeout:30000})
    await page.locator('.answer-input textarea,textarea.answer-input').fill('x=5')
    await page.getByRole('button',{name:'提交作答',exact:true}).click()
    await expect(page.getByText('再练一道',{exact:true})).toBeVisible({timeout:30000})
    const id=new URLSearchParams(page.url().split('?')[1]).get('id')
    const current=await page.request.get('http://127.0.0.1:8002/api/v1/learning-tasks/'+id,{headers:{Authorization:'Bearer '+token}})
    const task=(await current.json()).data
    const question=task.student_view.prompt_blocks.find(b=>b.kind==='question').text
    const answer=execFileSync(path.join(root,'.venv/bin/python'),['-c','import sys;from app.services.math_tools import solve_text_equation;answer,ok=solve_text_equation(sys.argv[1]);assert ok;print(answer)',question],{env:{...process.env,PYTHONPATH:path.join(root,'backend')}}).toString().trim()
    await page.locator('.answer-input textarea,textarea.answer-input').fill(answer)
    await page.getByRole('button',{name:'提交作答',exact:true}).click()
    await expect(page.getByText('本次学习完成',{exact:true})).toBeVisible({timeout:30000})
    await page.screenshot({path:path.join(output,'completed.png'),fullPage:true})
    const final=await page.request.get('http://127.0.0.1:8002/api/v1/learning-tasks/'+id,{headers:{Authorization:'Bearer '+token}})
    const result=(await final.json()).data
    expect(result.status).toBe('completed')
    expect(result.learning_applied).toBe(true)
    expect(errors).toEqual([])
    Object.assign(report,{passed:true,task_id:id,question_id:actor.question_id,learning_applied:result.learning_applied,browser_errors:errors})
    console.log('Actual diagnosis → correction → original retry → contrast → persisted learning passed')
  } finally {
    fs.writeFileSync(path.join(output,'../actual-flow.json'),JSON.stringify(report,null,2)+'\n')
    await browser.close()
  }
}
main().catch(error=>{ console.error(error.message);process.exitCode=1 })
