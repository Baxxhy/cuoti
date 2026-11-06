// Extends the original functional-audit desktop crop case to all corners and touch.
import {expect,test} from '@playwright/test'
const API=process.env.SCZX_API_URL||'http://127.0.0.1:8010/api/v1'
for(const mobile of [false,true])test.describe(mobile?'触屏裁剪':'电脑裁剪',()=>{
 test.use({viewport:{width:mobile?390:1280,height:mobile?844:900},screen:{width:mobile?390:1280,height:mobile?844:900},isMobile:mobile,hasTouch:mobile})
 test('四角调整、移动框选和整图恢复保留原图',async({page,request},info)=>{
  const email=`crop-${Date.now()}-${mobile}@example.test`,password='Crop-test-123'
  const registration=await request.post(API+'/auth/register',{data:{email,password,grade:'初二'}})
  expect(registration.ok()).toBe(true)
  const actor=(await registration.json()).data,headers={Authorization:`Bearer ${actor.access_token}`}
  await page.addInitScript(token=>localStorage.setItem('minddimension_access_token',JSON.stringify(token)),actor.access_token)
  await page.goto('/#/pages/capture/capture')
  const png=Buffer.from(await page.evaluate(()=>{const canvas=document.createElement('canvas');canvas.width=800;canvas.height=500;const c=canvas.getContext('2d')!;c.fillStyle='#fff';c.fillRect(0,0,800,500);c.fillStyle='#3157a8';c.font='32px sans-serif';c.fillText('2x + 3 = 11',60,100);return canvas.toDataURL().split(',')[1]}),'base64')
  const upload=await request.post(API+'/questions/ingest',{headers,multipart:{file:{name:'crop.png',mimeType:'image/png',buffer:png},defer_processing:'true'}})
  expect(upload.ok()).toBe(true)
  const question=(await upload.json()).data
  await page.goto('/#/pages/crop/crop?id='+question.question_id)
  const box=page.locator('.crop-box')
  await expect.poll(async()=>(await box.boundingBox())?.width||0).toBeGreaterThan(100)
  const session=mobile?await page.context().newCDPSession(page):null
  async function drag(x:number,y:number,dx:number,dy:number){
   if(session){
    await session.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x,y}]})
    for(let i=1;i<=8;i++)await session.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:x+dx*i/8,y:y+dy*i/8}]})
    await session.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]})
   }else{await page.mouse.move(x,y);await page.mouse.down();await page.mouse.move(x+dx,y+dy,{steps:8});await page.mouse.up()}
  }
  for(const [corner,dx,dy] of [['lt',25,20],['rt',-25,20],['lb',25,-20],['rb',-25,-20]] as const){
   const before=(await box.boundingBox())!,handle=(await page.locator('.corner.'+corner).boundingBox())!
   await drag(handle.x+handle.width/2,handle.y+handle.height/2,dx,dy)
   await expect.poll(async()=>(await box.boundingBox())!.width).toBeLessThan(before.width-10)
   await expect.poll(async()=>(await box.boundingBox())!.height).toBeLessThan(before.height-10)
   const reduced=(await box.boundingBox())!
   await drag(reduced.x+reduced.width/2,reduced.y+reduced.height/2,10,8)
   await expect.poll(async()=>(await box.boundingBox())!.x).toBeGreaterThan(reduced.x+3)
   await page.getByRole('button',{name:'选择整张图片',exact:true}).click()
   await expect.poll(async()=>(await box.boundingBox())!.width).toBeGreaterThan(before.width)
   // Return to the default inset before testing the next corner.
   await page.reload()
   await expect(box).toBeVisible()
   await expect.poll(async()=>(await box.boundingBox())!.width).toBeGreaterThan(100)
  }
  const detail=await (await request.get(API+'/questions/'+question.question_id,{headers})).json()
  const original=detail.data.assets.find((asset:any)=>asset.kind==='uploaded_original')
  expect(await (await request.get(new URL(original.url,API).href)).body()).toEqual(png)
  await page.screenshot({path:info.outputPath('crop-four-corners.png'),fullPage:true})
 })
})
