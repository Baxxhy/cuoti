// Render the original H5 build and migrated Vue build with identical controlled data.
import fs from 'node:fs'
import path from 'node:path'
import http from 'node:http'
import {fileURLToPath} from 'node:url'
import {createRequire} from 'node:module'
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..')
process.env.PLAYWRIGHT_BROWSERS_PATH ||= path.join(root,'.runtime/playwright-browsers')
const {chromium}=createRequire(path.join(root,'frontend/package.json'))('@playwright/test')
const original=process.env.SCZX_ORIGINAL_H5||path.resolve(root,'../frontend/dist/build/h5')
const artifacts=path.join(root,'.runtime/page-compare',process.env.SCZX_COMPARE_RUN||String(Date.now()))
fs.mkdirSync(artifacts,{recursive:true})
const user={id:'ui-user',name:'界面对照',email:'ui@example.test',grade:'初二',role:'student'}
const task={id:'ui-task',question_id:'ui-question',session_id:null,status:'completed',version:4,step_id:'ui-step',input_fingerprint:'ui-fingerprint',learning_applied:true,last_request_id:'ui-answer',current_action:'answer',exit_reason:'',restart_required:false,student_view:{title:'本次学习完成',feedback:'对照题独立完成了，已保留这次验证记录。',prompt_blocks:[],input_kind:'none',secondary_actions:[],recommendation:{action:'practice',question_id:'',knowledge_card_ids:[],reason:''}}}
const initial=['pages/login/login','pages/register/register','pages/forgot/forgot','pages/manual/manual','pages/manual/manual?ui_filled=1','pages/task/task?id=ui-task','pages/task/task?id=ui-task&ui_repair=1','pages/index/index']
const cases=process.env.SCZX_COMPARE_ROUTES?process.env.SCZX_COMPARE_ROUTES.split(','):process.argv.includes('--all')?[...JSON.parse(fs.readFileSync(path.join(root,'frontend/src/routes.json'))),...initial.filter(r=>r.includes('?'))]:initial
const mime={'.js':'text/javascript','.css':'text/css','.html':'text/html','.json':'application/json','.ttf':'font/ttf','.woff':'font/woff','.woff2':'font/woff2','.svg':'image/svg+xml','.png':'image/png'}
async function serve(folder){
 const server=http.createServer((req,res)=>{
  const pathname=decodeURIComponent(new URL(req.url,'http://local').pathname)
  let file=path.resolve(folder,'.'+(pathname==='/'?'/index.html':pathname))
  if(!file.startsWith(path.resolve(folder)+path.sep)){res.writeHead(403).end();return}
  if(!fs.existsSync(file)||!fs.statSync(file).isFile())file=path.join(folder,'index.html')
  res.setHeader('Content-Type',mime[path.extname(file)]||'application/octet-stream');res.end(fs.readFileSync(file))
 })
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve))
 return {server,base:'http://127.0.0.1:'+server.address().port}
}
const servers=[];const browser=await chromium.launch({args:['--no-sandbox']});const results=[]
try{
 for(const [name,folder] of [['original',original],['vue',path.join(root,'frontend/dist')]]){
  const service=await serve(folder);servers.push(service.server)
  for(const width of [390,1280])for(const route of cases){
   const anonymous=/pages\/(login|register|forgot)\//.test(route)
   const context=await browser.newContext({viewport:{width,height:width===390?844:900},reducedMotion:'reduce',deviceScaleFactor:1})
   await context.addInitScript(({name,anonymous})=>{if(!anonymous)localStorage.setItem('minddimension_access_token',name==='original'?'ui-token':JSON.stringify('ui-token'))},{name,anonymous})
   const page=await context.newPage();const errors=[]
   page.on('pageerror',e=>errors.push(e.message))
   await page.route('**/api/v1/**',async intercept=>{
    const url=new URL(intercept.request().url());let data,status=200
    if(url.pathname==='/api/v1/auth/me'){data={...user,role:/pages\/(admin|system)\//.test(route)?'admin':'student'};if(anonymous)status=401}
    else if(url.pathname==='/api/v1/learning-tasks/ui-task')data=route.includes('ui_repair')?{...task,status:'waiting_student',learning_applied:false,student_view:{title:'先订正这一步',feedback:'',prompt_blocks:[{kind:'question',text:'解方程 2x+3=11'}],input_kind:'text',secondary_actions:['hint','visualize']}}:task
    else if(url.pathname.endsWith('/self-check'))data={version:0,source_current:true,can_save:true,note:null}
    else if(url.pathname.endsWith('/history'))data={items:[],has_more:false,source_question:null}
    else status=503
    await intercept.fulfill({status,json:status===200?{success:true,data,error:null,request_id:'ui-fixed'}:{detail:status===401?'请先使用账号和密码登录':'界面对照：暂时无法读取'}})
   })
   await page.goto(service.base+'/#/'+route,{waitUntil:'networkidle'})
   if(route.includes('ui_filled')){const fields=page.locator('textarea');await fields.nth(0).fill('解方程 2x+3=11。\n先移项，再求出未知数。');await fields.nth(1).fill('x=7');await fields.nth(2).fill(Array.from({length:10},(_,i)=>'第'+(i+1)+'步：保留自己的计算过程。').join('\n'));await page.waitForTimeout(100)}
   if(route.includes('ui_modal')){await page.getByText('拍照与辅助工具',{exact:true}).click();await page.getByText('查看图解',{exact:true}).click()}
   await page.evaluate(()=>document.fonts.ready)
   await page.addStyleTag({content:'*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent!important}'})
   const snapshot=await page.evaluate(()=>{
    const fields=['fontFamily','fontSize','fontWeight','letterSpacing','textAlign','lineHeight','height','minHeight','paddingTop','paddingRight','paddingBottom','paddingLeft','marginTop','marginRight','marginBottom','marginLeft','borderTopWidth','borderRadius','display','backgroundColor','color']
    const items=[...document.querySelectorAll('button,uni-button,input:not([type="file"]),textarea,h1,h2,.auth-title,.auth-form,.context-row,.disclosure,.task-title,.page-header,.uni-icons,.uni-sample-toast,.uni-simple-toast__text,.web-toast,.web-toast-text,.uni-modal,.uni-modal__hd,.uni-modal__bd,.uni-modal__ft,.uni-modal__btn')].filter(e=>e.getBoundingClientRect().width&&e.getBoundingClientRect().height).map(e=>{
     const r=e.getBoundingClientRect(),css=getComputedStyle(e)
     return {tag:e.tagName,classes:e.className,text:(e.innerText||e.getAttribute('placeholder')||'').trim().replace(/\s+/g,' '),box:[r.x,r.y,r.width,r.height].map(v=>Math.round(v*100)/100),style:Object.fromEntries(fields.map(k=>[k,css[k]]))}
    })
    const words=[]
    function visit(node){
     if(node.nodeType===Node.TEXT_NODE){if(node.textContent.trim())words.push(node.textContent.trim());return}
     if(node.nodeType!==Node.ELEMENT_NODE||['SCRIPT','STYLE'].includes(node.tagName))return
     const css=getComputedStyle(node)
     if(css.display==='none'||css.visibility==='hidden'||css.opacity==='0'||node.getAttribute('aria-hidden')==='true')return
     if(['INPUT','TEXTAREA'].includes(node.tagName)){if(node.value||node.getAttribute('placeholder'))words.push(node.value||node.getAttribute('placeholder'));return}
     if(node.tagName==='SELECT'){if(node.selectedOptions[0])words.push(node.selectedOptions[0].text);return}
     node.childNodes.forEach(visit)
    }
    visit(document.body)
    return {text:words.join(' ').replace(/\s+/g,' '),overflow:document.documentElement.scrollWidth>innerWidth+1,items}
   })
   const key=route.replaceAll('/','-').replaceAll('?','-').replaceAll('=','-')+'-'+width
   await page.screenshot({path:path.join(artifacts,key+'-'+name+'.png')})
   let popupDismissed
   if(route.includes('ui_modal')){await page.locator('.uni-modal__btn_default').click();await page.waitForTimeout(350);popupDismissed=await page.locator('.uni-modal:visible').count()===0}
   results.push({name,route,width,popupDismissed,url:page.url().split('#')[1],errors,...snapshot})
   await context.close()
  }
 }
 const comparisons=results.filter(r=>r.name==='original').map(a=>{
  const b=results.find(r=>r.name==='vue'&&r.route===a.route&&r.width===a.width)
  return {route:a.route,width:a.width,textEqual:a.text===b.text,originalText:a.text,vueText:b.text,originalErrors:a.errors,vueErrors:b.errors,originalOverflow:a.overflow,vueOverflow:b.overflow,originalItems:a.items,vueItems:b.items,originalPopupDismissed:a.popupDismissed,vuePopupDismissed:b.popupDismissed}
 })
 fs.writeFileSync(path.join(artifacts,'report.json'),JSON.stringify(comparisons,null,2)+'\n')
 console.log(JSON.stringify({artifacts,cases:comparisons.length,textDifferences:comparisons.filter(c=>!c.textEqual).length,pageErrors:comparisons.filter(c=>c.originalErrors.length||c.vueErrors.length).length}))
}finally{await browser.close();await Promise.all(servers.map(s=>new Promise(resolve=>s.close(resolve))))}
