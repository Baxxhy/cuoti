<script setup>
import {ref,computed,watch,nextTick,onMounted,onBeforeUnmount} from 'vue'
import {createPickerMotion} from './picker-motion.js'
const props=defineProps({range:{type:Array,default:()=>[]},rangeKey:String,value:[String,Number,Array],mode:String,disabled:Boolean})
const emit=defineEmits(['change','cancel'])
const host=ref(null),list=ref(null),content=ref(null),open=ref(false),selected=ref(0),draft=ref(0),desktop=ref(false),position=ref({}),triangle=ref({})
let drag=null,previousFocus,suppressClick=false,wheelDelta=0,motion=null
const labels=computed(()=>props.range.map(item=>typeof item==='object'?(item?.[props.rangeKey]??''):String(item)))
const valid=value=>Math.max(0,Math.min(labels.value.length-1,Number(value)||0))
watch([()=>props.value,()=>props.range],([value])=>{selected.value=valid(value)},{immediate:true})
const documentTarget=document.getElementById('web-picker-layer')?'#web-picker-layer':'body'
const native=computed(()=>props.mode==='date'||props.mode==='time')
function close(){motion?.stop();motion=null;open.value=false;drag=null;previousFocus?.focus?.()}
function cancel(){close();emit('cancel',{detail:{}})}
function confirm(event){selected.value=draft.value;close();emit('change',{detail:{value:selected.value},target:event?.target})}
function choose(index,event){draft.value=index;if(desktop.value)confirm(event)}
async function show(){
 if(props.disabled||native.value||open.value)return
 wheelDelta=0;previousFocus=document.activeElement;draft.value=valid(selected.value)
 desktop.value=innerWidth>=500&&innerHeight>=500
 const r=host.value.getBoundingClientRect(),above=r.top+r.height-innerHeight/2>innerHeight/2-r.top
 position.value=desktop.value?{transform:'none',left:Math.max(0,r.left)+'px',width:r.width+'px',top:above?'auto':r.bottom+6+'px',bottom:above?innerHeight-r.top+6+'px':'auto'}:{}
 triangle.value=desktop.value?{left:Math.max(12,Math.min(r.width-12,r.width/2))+'px',...(above?{bottom:'-6px',borderWidth:'6px 6px 0',borderColor:'#fcfcfd transparent transparent'}:{top:'-6px',borderWidth:'0 6px 6px',borderColor:'transparent transparent #fcfcfd'})}:{}
 open.value=true;await nextTick();if(list.value)list.value.scrollTop=draft.value*34
 if(!desktop.value&&content.value)motion=createPickerMotion(content.value,labels.value.length,draft.value,index=>{draft.value=index})
}
function wheel(event){wheelDelta+=event.deltaY;if(Math.abs(wheelDelta)>10){draft.value=valid(draft.value+Math.sign(wheelDelta));motion?.select(draft.value);wheelDelta=0}}
function activate(event){if(native.value)return;event.preventDefault();event.stopPropagation();if(open.value){if(event.key==='Enter')confirm(event)}else show()}
function down(event){suppressClick=false;drag={y:event.clientY};motion?.start(event.clientY,event.timeStamp);event.currentTarget.setPointerCapture?.(event.pointerId)}
function move(event){if(drag){if(Math.abs(drag.y-event.clientY)>4)suppressClick=true;motion?.move(event.clientY,event.timeStamp)}}
function up(event){if(drag)motion?.end(event.clientY);drag=null}
function tap(event){if(!suppressClick&&!motion?.scrolling()){const offset=event.clientY-event.currentTarget.getBoundingClientRect().top-119;if(Math.abs(offset)>17)draft.value=valid(draft.value+Math.sign(offset)*Math.ceil((Math.abs(offset)-17)/34));motion?.select(draft.value)}suppressClick=false}
function key(event){
 if(!open.value)return
 if(event.key==='Escape'){event.preventDefault();cancel()}
 else if(['ArrowDown','ArrowUp'].includes(event.key)){event.preventDefault();draft.value=valid(draft.value+(event.key==='ArrowDown'?1:-1));motion?.select(draft.value)}
 else if(event.key==='Enter'){event.preventDefault();confirm(event)}
}
onMounted(()=>window.addEventListener('keydown',key))
onBeforeUnmount(()=>{motion?.stop();window.removeEventListener('keydown',key)})
</script>
<template>
 <div ref="host" class="web-picker" :role="native?undefined:'button'" :tabindex="disabled||native?undefined:0" :aria-disabled="disabled||undefined" :aria-expanded="native?undefined:open" @click="show" @keydown.enter="activate" @keydown.space="activate">
  <slot />
  <input v-if="native" class="web-picker-control" :type="mode" :value="value" :disabled="disabled" :min="$attrs.start" :max="$attrs.end" @change="emit('change',{detail:{value:$event.target.value},target:$event.target})" />
  <Teleport :to="documentTarget">
   <div v-if="open" class="web-selector" role="dialog" aria-label="选择选项" @click.stop @wheel.prevent @touchmove.prevent>
    <div class="web-selector-mask" @click="cancel" />
    <div class="web-selector-popup" :style="position" @click.stop>
     <div class="web-selector-header"><div class="web-selector-action cancel" role="button" tabindex="0" @click="cancel" @keydown.enter.stop.prevent="cancel">取消</div><div class="web-selector-action confirm" role="button" tabindex="0" @click="confirm" @keydown.enter.stop.prevent="confirm">完成</div></div>
     <div class="web-selector-wheel" @click="tap" @wheel.stop.prevent="wheel" @pointerdown="down" @pointermove="move" @pointerup="up" @pointercancel="up">
      <div class="web-selector-column">
       <div class="web-selector-wheel-mask" /><div class="web-selector-indicator" />
       <div ref="content" class="web-selector-content" style="transform:translateY(0px) translateZ(0)"><div v-for="(label,index) in labels" :key="index" class="web-selector-item">{{label}}</div></div>
      </div>
     </div>
     <div ref="list" class="web-selector-list" role="listbox" @wheel.stop @touchmove.stop><div v-for="(label,index) in labels" :key="index" class="web-selector-item" :class="{selected:draft===index}" role="option" :aria-selected="draft===index" @click="choose(index,$event)">{{label}}</div></div>
     <div v-if="desktop" class="web-selector-triangle" :style="triangle" />
    </div>
   </div>
  </Teleport>
 </div>
</template>
<style src="./web-picker.css"></style>
