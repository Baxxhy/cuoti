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
const initial=['pages/manual/manual?ui_picker=1','pages/manual/manual?ui_picker=2','pages/framework/framework?ui_picker=1','pages/login/login','pages/register/register','pages/forgot/forgot','pages/manual/manual','pages/manual/manual?ui_filled=1','pages/task/task?id=ui-task','pages/task/task?id=ui-task&ui_repair=1','pages/index/index','pages/task/task?id=ui-task&ui_repair=1&ui_modal=1','pages/detail/detail?id=ui-question&ui_sheet=1','pages/detail/detail?id=ui-question&ui_remove=1','pages/detail/detail?id=ui-question&ui_preview=1','pages/capture/capture?ui_return=1','pages/capture/capture?ui_history=1']
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
   const page=await context.newPage();const errors=[];const writes=[]
   page.on('pageerror',e=>errors.push(e.message))
   await page.route('**/ui-preview-*.png',async intercept=>{const second=intercept.request().url().includes('-b.');await intercept.fulfill({contentType:'image/svg+xml',body:`<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360"><rect width="640" height="360" fill="${second?'#e8d8b0':'#bdd8ed'}"/><path d="M80 280 L320 60 L560 280 Z" fill="none" stroke="#3157a8" stroke-width="8"/></svg>`})})
   await page.route('**/api/v1/**',async intercept=>{
    const url=new URL(intercept.request().url());let data,status=200
    if(!['GET','HEAD'].includes(intercept.request().method()))writes.push({method:intercept.request().method(),path:url.pathname})
    if(url.pathname==='/api/v1/auth/me'){data={...user,role:/pages\/(admin|system)\//.test(route)?'admin':'student'};if(anonymous)status=401}
    else if(url.pathname==='/api/v1/learning-tasks/ui-task')data=route.includes('ui_repair')?{...task,status:'waiting_student',learning_applied:false,student_view:{title:'先订正这一步',feedback:'',prompt_blocks:[{kind:'question',text:'解方程 2x+3=11'}],input_kind:'text',secondary_actions:['hint','visualize']}}:task
    else if(url.pathname==='/api/v1/questions/ui-question')data={id:'ui-question',subject:'数学',grade:'初二',question_text:'解方程 2x+3=11。',student_answer:'x=7',student_steps:[],assets:(route.includes('ui_preview')||route.includes('ui_crop'))?[{kind:'original',url:service.base+'/ui-preview-a.png'},{kind:'crop',url:service.base+'/ui-preview-b.png'}]:[],options:[],knowledge_points:['一元一次方程'],analysis:null,diagnosis:null}
    else if(url.pathname==='/api/v1/questions/ui-question/journey')data={stages:[],summary:'尚未开始学习'}
    else if(url.pathname.endsWith('/self-check'))data={version:0,source_current:true,can_save:true,note:null}
    else if(url.pathname.endsWith('/history'))data={items:[],has_more:false,source_question:null}
    else status=503
    await intercept.fulfill({status,json:status===200?{success:true,data,error:null,request_id:'ui-fixed'}:{detail:status===401?'请先使用账号和密码登录':'界面对照：暂时无法读取'}})
   })
   await page.goto(service.base+'/#/'+route,{waitUntil:'networkidle'})
   if(route.includes('ui_filled')){const fields=page.locator('textarea');await fields.nth(0).fill('解方程 2x+3=11。\n先移项，再求出未知数。');await fields.nth(1).fill('x=7');await fields.nth(2).fill(Array.from({length:10},(_,i)=>'第'+(i+1)+'步：保留自己的计算过程。').join('\n'));await page.waitForTimeout(100)}
   if(route.includes('ui_modal')){await page.getByText('拍照与辅助工具',{exact:true}).click();await page.getByText('查看图解',{exact:true}).click()}
   if(route.includes('ui_sheet')||route.includes('ui_remove')){await page.getByLabel('更多操作',{exact:true}).click();await page.waitForTimeout(350);if(route.includes('ui_remove'))await page.getByText('移出错题本',{exact:true}).click()}
   if(route.includes('ui_preview')){await page.getByText('查看原图',{exact:true}).click();await page.waitForTimeout(400)}
   if(route.includes('ui_return')){
    const chooser=page.waitForEvent('filechooser')
    await page.getByLabel('选择错题图片',{exact:true}).click()
    await (await chooser).setFiles({name:'return.png',mimeType:'image/png',buffer:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl6whkAAAAASUVORK5CYII=','base64')})
    await page.getByLabel('手动录入错题',{exact:true}).click()
    await page.locator('textarea').first().fill('离开后返回时保留上一页图片')
    await page.getByLabel('返回',{exact:true}).click()
    await page.waitForURL('**/#/pages/capture/capture*')
    await page.waitForTimeout(150)
    if(await page.locator('.capture-zone-selected').count()!==1)throw new Error(name+': selected photo lost on return')
   }
   if(route.includes('ui_history')){
    await page.getByLabel('手动录入错题',{exact:true}).click()
    await page.locator('textarea:visible').first().fill('浏览器返回检查')
    await page.goBack();await page.waitForURL('**/#/pages/capture/capture*')
    await page.goForward();await page.waitForURL('**/#/pages/manual/manual')
    await page.locator('textarea:visible').first().waitFor()
    await page.evaluate(()=>{location.hash='/pages/help/help?ui_direct=1'})
    await page.waitForURL('**/#/pages/help/help?ui_direct=1')
    await page.waitForTimeout(150)
    await page.reload({waitUntil:'networkidle'})
    const title=page.locator('.header-title:visible')
    if(await title.textContent()!=='使用指南')throw new Error(name+': stale page stack overrides the address after reload')
   }
   if(route.includes('ui_crop')){
    const handle=await page.locator('.corner.rb').boundingBox()
    await page.mouse.move(handle.x+handle.width/2,handle.y+handle.height/2);await page.mouse.down();await page.mouse.move(handle.x+handle.width/2-25,handle.y+handle.height/2-20,{steps:8});await page.mouse.up()
    const box=await page.locator('.crop-box').boundingBox()
    await page.mouse.move(box.x+box.width/2,box.y+box.height/2);await page.mouse.down();await page.mouse.move(box.x+box.width/2+10,box.y+box.height/2+8,{steps:8});await page.mouse.up()
   }
   if(route.includes('ui_picker')){await page.locator(name==='original'?'uni-picker':'.web-picker').nth(Number(new URLSearchParams(route.split('?')[1]).get('ui_picker'))-1).click();await page.waitForTimeout(1200)}
   await page.evaluate(()=>document.fonts.ready)
   await page.addStyleTag({content:'*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent!important}'})
   if(name==='vue'&&process.env.SCZX_COMPARE_VUE_CSS)await page.addStyleTag({content:process.env.SCZX_COMPARE_VUE_CSS})
   const snapshot=await page.evaluate(()=>{
    const fields=['fontFamily','fontSize','fontWeight','letterSpacing','textAlign','lineHeight','height','minHeight','paddingTop','paddingRight','paddingBottom','paddingLeft','marginTop','marginRight','marginBottom','marginLeft','borderTopWidth','borderRadius','display','backgroundColor','color','alignContent','alignItems','justifyContent','appearance','wordSpacing','whiteSpace','fontVariantNumeric','transform','transformOrigin','imageRendering','objectFit','width','maxWidth','maxHeight']
    const items=[...document.querySelectorAll('button,uni-button,input:not([type="file"]),textarea,h1,h2,.auth-title,.auth-form,.context-row,.disclosure,.task-title,.page-header,.uni-icons,.uni-sample-toast,.uni-simple-toast__text,.web-toast,.web-toast-text,.uni-modal,.uni-modal__hd,.uni-modal__bd,.uni-modal__ft,.uni-modal__btn,.uni-actionsheet,.uni-actionsheet__cell,.web-image-preview img,#u-a-p img,.crop-stage,.crop-box,.filter-button,.filter-label,.uni-input-placeholder,.uni-textarea-placeholder,.web-input-placeholder,.uni-picker-custom,.uni-picker-item,.uni-picker-header,.web-selector-popup,.web-selector-item,.web-selector-header,.uni-picker-view-content,.web-selector-content')].filter(e=>e.getBoundingClientRect().width&&e.getBoundingClientRect().height).map(e=>{
     const r=e.getBoundingClientRect(),css=getComputedStyle(e)
     const walker=document.createTreeWalker(e,NodeFilter.SHOW_TEXT);let textNode
     while((textNode=walker.nextNode())&&!textNode.textContent.trim()){}
     let textBox=null
     if(textNode){const range=document.createRange();range.selectNodeContents(textNode);const b=range.getBoundingClientRect();textBox=[b.x,b.y,b.width,b.height].map(v=>Math.round(v*100)/100)}
     const placeholder=e.tagName==='INPUT'?getComputedStyle(e,'::placeholder'):null
     const imageAncestors=e.tagName==='IMG'?[...function*(node){while(node&&node!==document.body){const c=getComputedStyle(node);yield {tag:node.tagName,classes:node.className,transform:c.transform,transformOrigin:c.transformOrigin,width:c.width,height:c.height};node=node.parentElement}}(e.parentElement)]:undefined
     return {imageAncestors,placeholderStyle:placeholder?Object.fromEntries(fields.map(k=>[k,placeholder[k]])):null,textBox,tag:e.tagName,classes:e.className,text:(e.innerText||e.getAttribute('placeholder')||'').trim().replace(/\s+/g,' '),box:[r.x,r.y,r.width,r.height].map(v=>Math.round(v*100)/100),style:Object.fromEntries(fields.map(k=>[k,css[k]]))}
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
   let popupDismissed,previewGestures,pickerInteraction
   if(route.includes('ui_picker')&&!process.env.SCZX_PICKER_VISUAL_ONLY){
    const picker=page.locator(name==='original'?'uni-picker':'.web-picker').nth(Number(new URLSearchParams(route.split('?')[1]).get('ui_picker'))-1)
    const mask=page.locator(name==='original'?'.uni-picker-mask:visible':'.web-selector-mask:visible')
    const before=(await picker.innerText()).trim()
    await mask.click({position:{x:1,y:1}});await page.waitForTimeout(350)
    if(await mask.isVisible())throw new Error(name+': picker cancellation did not close popup')
    if((await picker.innerText()).trim()!==before)throw new Error(name+': picker cancellation changed value')
    await picker.click();await page.waitForTimeout(400)
    const options=page.locator(width>=500?(name==='original'?'.uni-picker-custom:visible .uni-picker-select .uni-picker-item':'.web-selector-list .web-selector-item'):(name==='original'?'.uni-picker-custom:visible .uni-picker-view-content .uni-picker-item':'.web-selector-content .web-selector-item'))
    const index=Math.min(2,(await options.count())-1),chosen=(await options.nth(index).innerText()).trim()
    await options.nth(index).click();await page.waitForTimeout(350)
    if(width<500){
     if((await picker.innerText()).trim()!==before)throw new Error(name+': mobile picker applied selection before confirmation')
     await page.locator(name==='original'?'.uni-picker-action-confirm:visible':'.web-selector-action.confirm').click();await page.waitForTimeout(350)
    }
    if(await mask.isVisible())throw new Error(name+': picker confirmation did not close popup')
    if(!(await picker.innerText()).includes(chosen))throw new Error(name+': picker did not apply selected label '+chosen)
    pickerInteraction={cancelPreservedValue:true,confirmationApplied:true,chosen,index}
   }
   if(route.includes('ui_modal')||route.includes('ui_remove')){await page.locator('.uni-modal__btn_default').click();await page.waitForTimeout(350);popupDismissed=await page.locator('.uni-modal:visible').count()===0}
   if(route.includes('ui_sheet')){await page.locator(name==='original'?'.uni-actionsheet__mask':'.web-popup-mask').click({position:{x:1,y:1}});await page.waitForTimeout(350);popupDismissed=await page.locator('.uni-actionsheet_toggle:visible').count()===0}
   if(route.includes('ui_preview')){
    await page.mouse.move(width-15,(width===390?844:900)/2)
    await page.locator(name==='original'?'.uni-swiper-navigation-next':'.web-preview-navigation.is-next').click()
    await page.waitForTimeout(650)
    const switched=await page.evaluate(()=>[...document.querySelectorAll('#u-a-p img,.web-image-preview img')].some(img=>{const r=img.getBoundingClientRect();return img.src.includes('ui-preview-b.png')&&Math.abs(r.x+r.width/2-innerWidth/2)<2}))
    if(!switched)throw new Error(name+': gallery did not switch to second image')
    await page.screenshot({path:path.join(artifacts,key+'-'+name+'-second.png')})
    if(name==='vue'){
     const picture=page.locator('.web-preview-image')
     const before=await picture.boundingBox()
     const touch=await context.newCDPSession(page)
     const point=(id,x,y)=>({id,x,y,radiusX:1,radiusY:1,force:1})
     await touch.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[point(1,100,300)]})
     await touch.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[point(1,100,300),point(2,150,300)]})
     await touch.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[point(1,100,300),point(2,300,300)]})
     await page.waitForTimeout(100)
     const zoomed=await picture.boundingBox()
     if(Math.abs(zoomed.width-before.width*4)>1||Math.abs(zoomed.height-before.height*4)>1)throw new Error('Vue preview pinch did not enlarge image fourfold')
     await touch.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]})
     await touch.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[point(3,200,400)]})
     await touch.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[point(3,280,410)]})
     await page.waitForTimeout(100)
     const panned=await picture.boundingBox()
     if(Math.abs(panned.x-zoomed.x-80)>1||Math.abs(panned.y-zoomed.y-10)>1)throw new Error('Vue preview enlarged image did not follow drag')
     await touch.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]})
     await touch.detach()
     await page.mouse.move(15,(width===390?844:900)/2)
     await page.locator('.web-preview-navigation:not(.is-next)').click()
     const reset=await picture.boundingBox()
     if(Math.abs(reset.width-before.width)>1||Math.abs(reset.x-before.x)>1||Math.abs(reset.y-before.y)>1)throw new Error('Vue preview did not reset zoom and position after switching images')
     previewGestures={input:'Chromium touch events',before,zoomed,panned,reset}
    }
    await page.keyboard.press('Escape');await page.waitForTimeout(100);popupDismissed=await page.locator(name==='original'?'#u-a-p img':'.web-image-preview').count()===0}
   if(/ui_modal|ui_sheet|ui_remove|ui_preview/.test(route)){if(!popupDismissed)throw new Error(name+': popup did not dismiss');if(writes.length)throw new Error(name+': cancellation issued a write request')}
   results.push({name,route,width,popupDismissed,previewGestures,pickerInteraction,writes,url:page.url().split('#')[1],errors,...snapshot})
   await context.close()
  }
 }
 const comparisons=results.filter(r=>r.name==='original').map(a=>{
  const b=results.find(r=>r.name==='vue'&&r.route===a.route&&r.width===a.width)
  return {route:a.route,width:a.width,vueStyleOverride:process.env.SCZX_COMPARE_VUE_CSS||null,pickerVisualOnly:!!process.env.SCZX_PICKER_VISUAL_ONLY,textEqual:a.text===b.text,originalText:a.text,vueText:b.text,originalErrors:a.errors,vueErrors:b.errors,originalOverflow:a.overflow,vueOverflow:b.overflow,originalItems:a.items,vueItems:b.items,originalPopupDismissed:a.popupDismissed,vuePopupDismissed:b.popupDismissed,vuePreviewGestures:b.previewGestures,originalPickerInteraction:a.pickerInteraction,vuePickerInteraction:b.pickerInteraction,originalWrites:a.writes,vueWrites:b.writes}
 })
 fs.writeFileSync(path.join(artifacts,'report.json'),JSON.stringify(comparisons,null,2)+'\n')
 console.log(JSON.stringify({artifacts,cases:comparisons.length,textDifferences:comparisons.filter(c=>!c.textEqual).length,pageErrors:comparisons.filter(c=>c.originalErrors.length||c.vueErrors.length).length}))
}finally{await browser.close();await Promise.all(servers.map(s=>new Promise(resolve=>s.close(resolve))))}
