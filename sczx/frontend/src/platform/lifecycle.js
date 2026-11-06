import {inject,onMounted,onBeforeUnmount,watch} from 'vue'
import {parsePage} from './browser.js'
import {pageContext} from './page-context.js'
export function onLoad(callback){
 const context=inject(pageContext,null)
 const options=context?.options||parsePage(window.location.hash.slice(1)).options
 onMounted(()=>callback(options))
}
function visibilityHook(callback,shown){
 const context=inject(pageContext,null)
 let mounted=false,visible=false
 function update(){
  const next=(context?.active.value??true)&&document.visibilityState!=='hidden'
  if(next!==visible){visible=next;if(next===shown)callback()}
 }
 onMounted(()=>{mounted=true;update()})
 const stop=context?watch(context.active,()=>{if(mounted)update()},{flush:'post'}):()=>{}
 document.addEventListener('visibilitychange',update)
 onBeforeUnmount(()=>{stop();document.removeEventListener('visibilitychange',update);if(visible&&!shown)callback();mounted=false})
}
export function onShow(callback){visibilityHook(callback,true)}
export function onHide(callback){visibilityHook(callback,false)}
export function onUnload(callback){onBeforeUnmount(callback)}
