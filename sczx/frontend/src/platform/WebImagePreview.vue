<script setup>
import {ref,watch,onMounted,onBeforeUnmount} from 'vue'
import {imagePreviewState as preview,browser} from './browser.js'
import {previewIcons} from './preview-icons.js'
const scale=ref(1),x=ref(0),y=ref(0),showNavigation=ref(false),image=ref(null)
const pointers=new Map()
let start=null,pinch=null,suppressClick=false,hideTimer,previousOverflow
function reset(){scale.value=1;x.value=0;y.value=0;pointers.clear();pinch=null;start=null}
watch(preview,(value,old)=>{
 reset()
 if(value&&!old){previousOverflow=document.body.style.overflow;document.body.style.overflow='hidden'}
 if(!value&&old)document.body.style.overflow=previousOverflow
},{immediate:true})
function close(){browser.closePreviewImage()}
function next(delta){
 const value=preview.value;if(!value)return
 const index=value.index+delta
 if(index>=0&&index<value.urls.length){preview.value={...value,index};reset()}
}
function clampPan(){
 const el=image.value;if(!el)return
 const maxX=Math.max(0,(el.offsetWidth*scale.value-innerWidth)/2),maxY=Math.max(0,(el.offsetHeight*scale.value-innerHeight)/2)
 x.value=Math.max(-maxX,Math.min(maxX,x.value));y.value=Math.max(-maxY,Math.min(maxY,y.value))
}
function distance(){const [a,b]=[...pointers.values()];return Math.hypot(a.x-b.x,a.y-b.y)}
function down(e){
 if(e.target.closest('[role="button"]'))return
 suppressClick=false
 pointers.set(e.pointerId,{x:e.clientX,y:e.clientY})
 e.currentTarget.setPointerCapture?.(e.pointerId)
 if(pointers.size===1)start={x:e.clientX,y:e.clientY,panX:x.value,panY:y.value}
 if(pointers.size===2){pinch={distance:distance(),scale:scale.value};suppressClick=true}
}
function move(e){
 if(!pointers.has(e.pointerId))return
 pointers.set(e.pointerId,{x:e.clientX,y:e.clientY})
 if(pointers.size===2&&pinch){scale.value=Math.max(1,Math.min(4,pinch.scale*distance()/Math.max(1,pinch.distance)));clampPan();suppressClick=true;return}
 if(!start)return
 const dx=e.clientX-start.x,dy=e.clientY-start.y
 if(Math.abs(dx)>20||Math.abs(dy)>20)suppressClick=true
 if(scale.value>1){x.value=start.panX+dx;y.value=start.panY+dy;clampPan()}
}
function up(e){
 if(start&&!pinch&&scale.value===1){const dx=e.clientX-start.x,dy=e.clientY-start.y;if(Math.abs(dx)>40&&Math.abs(dx)>Math.abs(dy)){next(dx<0?1:-1);suppressClick=true}}
 pointers.delete(e.pointerId)
 if(!pointers.size){start=null;pinch=null}
}
function clicked(){if(!suppressClick)close();suppressClick=false}
function hover(e){
 clearTimeout(hideTimer)
 if(preview.value?.urls.length<2)return
 if(e.clientX<innerWidth/3||e.clientX>innerWidth*2/3)showNavigation.value=true
 else hideTimer=setTimeout(()=>{showNavigation.value=false},300)
}
function key(e){if(preview.value&&e.key==='Escape')close()}
onMounted(()=>window.addEventListener('keyup',key))
onBeforeUnmount(()=>{window.removeEventListener('keyup',key);clearTimeout(hideTimer);if(preview.value)document.body.style.overflow=previousOverflow})
</script>
<template>
 <div v-if="preview" class="web-image-preview" role="dialog" aria-modal="true" aria-label="图片预览" @click="clicked" @pointerdown="down" @pointermove="move" @pointerup="up" @pointercancel="pointers.clear();start=null;pinch=null" @mousemove="hover" @mouseleave="showNavigation=false">
  <div class="web-preview-motion" :style="{transform:`translateX(${x}px) translateY(${y}px) translateZ(0px) scale(${scale})`}">
  <img ref="image" class="web-preview-image" :src="preview.urls[preview.index]" alt="" draggable="false" style="transform:translate(-50%,-50%)" @load="clampPan" />
  </div>
  <div v-for="(delta,i) in [-1,1]" :key="delta" class="web-preview-navigation" :class="{'is-next':i===1,'is-disabled':delta<0?preview.index===0:preview.index===preview.urls.length-1,'is-hidden':!showNavigation}" role="button" tabindex="0" :aria-label="i?'下一张':'上一张'" :aria-disabled="delta<0?preview.index===0:preview.index===preview.urls.length-1" @click.stop="next(delta)" @keydown.enter.prevent="next(delta)">
   <svg width="26" height="26" viewBox="0 0 32 32"><path :d="previewIcons.BACK" fill="#ffffff" /></svg>
  </div>
  <div class="web-preview-close" role="button" tabindex="0" aria-label="关闭图片预览" @click.stop="close" @keydown.enter.prevent="close"><svg width="26" height="26" viewBox="0 0 32 32"><path :d="previewIcons.CLOSE" fill="#ffffff" /></svg></div>
 </div>
</template>
<style>
.web-image-preview {display:block;position:fixed;left:0;top:0;width:100%;height:100%;z-index:999;background:rgba(0,0,0,.8);touch-action:none;overflow:hidden;}
.web-preview-motion {position:absolute;left:0;top:0;width:100%;height:100%;}
.web-preview-image {position:absolute;left:50%;top:50%;max-width:100%;max-height:100%;user-select:none;}
.web-preview-close {position:absolute;box-sizing:border-box;top:0;right:0;width:60px;height:44px;padding:6px;line-height:32px;font-size:26px;color:white;text-align:center;cursor:pointer;}
.web-preview-navigation {width:26px;height:26px;cursor:pointer;position:absolute;top:50%;margin-top:-13px;display:flex;align-items:center;border-radius:50%;left:10px;}
.web-preview-navigation:hover {background:rgba(53,53,53,.6)}
.web-preview-navigation svg {margin-left:-1px}
.web-preview-navigation.is-next {left:auto;right:10px}
.web-preview-navigation.is-next svg {margin-left:0;transform:rotate(180deg)}
.web-preview-navigation.is-disabled {opacity:.35;cursor:not-allowed}
.web-preview-navigation.is-hidden {opacity:0;pointer-events:none}
</style>
