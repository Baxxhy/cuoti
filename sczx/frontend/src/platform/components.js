import { h, defineComponent, provide, inject, ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { fontData } from './icons.js'
const eventValue = (event, value) => ({ detail: { value }, target: event.target, preventDefault: () => event.preventDefault(), stopPropagation: () => event.stopPropagation() })
function field(tag) {
 return defineComponent({inheritAttrs:false,
 props:{modelValue:[String,Number],value:[String,Number],password:Boolean,focus:Boolean,cursor:{type:Number,default:-1},autoHeight:Boolean},
 emits:['input','change','confirm','focus','blur','update:modelValue'],
 setup(props,{attrs,emit}) {
  const host=ref(null),control=ref(null),inputText=ref(props.modelValue??props.value??'')
  let observer,lastWidth=-1
  function resize(){
   if(tag!=='textarea'||!props.autoHeight||!host.value||!control.value)return
   const css=getComputedStyle(host.value),number=k=>parseFloat(css[k])||0
   const extra=number('paddingTop')+number('paddingBottom')+number('borderTopWidth')+number('borderBottomWidth')
   control.value.style.height='0px'
   const content=Math.max(number('minHeight'),control.value.value?control.value.scrollHeight:(number('lineHeight')||number('fontSize')*1.2))
   host.value.style.height=(content+extra)+'px';control.value.style.height=content+'px'
  }
  function selection(){
   if(!control.value)return
   if(props.focus)control.value.focus()
   if(props.cursor>=0)try{control.value.setSelectionRange(props.cursor,props.cursor)}catch{}
  }
  onMounted(()=>{nextTick(()=>{resize();selection()});document.fonts?.ready.then(resize);if(typeof ResizeObserver!=='undefined'){observer=new ResizeObserver(entries=>{const width=entries[0].contentRect.width;if(width!==lastWidth){lastWidth=width;resize()}});observer.observe(host.value)}})
  onBeforeUnmount(()=>observer?.disconnect())
  watch(()=>props.modelValue??props.value,value=>{inputText.value=value??'';nextTick(resize)})
  watch(()=>[props.focus,props.cursor],selection,{flush:'post'})
  function event(e){return {...eventValue(e,e.target.value),detail:{value:e.target.value,cursor:e.target.selectionStart}}}
  return()=>{
   const {class:classes,style,...rest}=attrs
   const type=props.password?'password':rest.type==='digit'?'text':rest.type
   const overlay=tag==='input'&&typeof rest.placeholder==='string'&&rest.placeholder.length>0
   const value=overlay?inputText.value:props.modelValue??props.value??''
   const native=h(tag,{...rest,ref:control,class:tag==='textarea'?'uni-textarea-textarea':'uni-input-input',type,inputmode:rest.inputmode||(rest.type==='digit'?'decimal':undefined),value,
    onInput:e=>{if(overlay)inputText.value=e.target.value;emit('update:modelValue',e.target.value);emit('input',event(e));resize()},
    onChange:e=>emit('change',event(e)),onFocus:e=>emit('focus',event(e)),onBlur:e=>emit('blur',event(e)),
    onKeydown:e=>{rest.onKeydown?.(e);if(e.key==='Enter')emit('confirm',event(e))}})
   const children=overlay?[h('div',{class:'web-input-core'},[
    h('div',{class:'web-input-placeholder input-placeholder','aria-hidden':'true',style:{display:value===''?'block':'none'}},rest.placeholder),native
   ])]:[native]
   return h('div',{ref:host,class:[tag==='textarea'?'web-textarea':'web-input',classes],style,onClick:e=>{if(e.target===host.value&&!rest.disabled){control.value?.focus();rest.onClick?.(e)}}},children)
  }
 }
 })
}
export const WebInput=field('input'),WebTextarea=field('textarea')
export const WebImage=defineComponent({inheritAttrs:false,props:{src:String,mode:String},emits:['load','error'],setup(p,{attrs,emit}){return()=>h('img',{...attrs,src:p.src,style:[{objectFit:p.mode==='aspectFill'?'cover':'contain',height:p.mode==='widthFix'?'auto':undefined},attrs.style],onLoad:e=>emit('load',{detail:{width:e.target.naturalWidth,height:e.target.naturalHeight}}),onError:e=>emit('error',e)})}})
const glyphs=Object.fromEntries(fontData.map(x=>[x.font_class,x.unicode]))
export const WebIcon=defineComponent({props:{type:String,size:[String,Number],color:{type:String,default:'#333333'}},setup(p){return()=>h('span',{class:'web-icon uni-icons',style:{fontSize:(p.size||16)+'px',color:p.color},'aria-hidden':'true','data-glyph':glyphs[p.type]||''}) }})
export const WebLoadMore=defineComponent({props:{status:String,contentText:Object},setup(p){return()=>h('div',{role:'status',class:'web-loading'},p.contentText?.contentrefresh||'正在加载')}})
export const WebPicker=defineComponent({inheritAttrs:false,props:{range:{type:Array,default:()=>[]},rangeKey:String,value:[String,Number,Array],mode:String,disabled:Boolean},emits:['change'],setup(p,{attrs,slots,emit}){
 return()=>h('div',{...attrs,class:[attrs.class,'web-picker']},[slots.default?.(),p.mode==='date'||p.mode==='time'?h('input',{class:'web-picker-control',type:p.mode,value:p.value,disabled:p.disabled,min:attrs.start,max:attrs.end,onChange:e=>emit('change',eventValue(e,e.target.value))}):h('select',{class:'web-picker-control',value:p.value??0,disabled:p.disabled,'aria-label':attrs['aria-label']||'选择选项',onChange:e=>emit('change',eventValue(e,Number(e.target.value)))},p.range.map((x,i)=>h('option',{value:i},p.rangeKey?x[p.rangeKey]:String(x))))])
}})
export const WebScroll=defineComponent({inheritAttrs:false,props:{scrollX:Boolean,scrollY:Boolean},setup(p,{attrs,slots}){return()=>h('div',{...attrs,style:[{overflowX:p.scrollX?'auto':undefined,overflowY:p.scrollY?'auto':undefined},attrs.style]},slots.default?.())}})
export const WebSlider=defineComponent({inheritAttrs:false,props:{value:Number,min:Number,max:Number,step:Number},emits:['changing','change'],setup(p,{attrs,emit}){return()=>h('input',{...attrs,type:'range',value:p.value,min:p.min,max:p.max,step:p.step,onInput:e=>emit('changing',eventValue(e,Number(e.target.value))),onChange:e=>emit('change',eventValue(e,Number(e.target.value)))})}})
const groupKey=Symbol('choiceGroup')
let groupCount=0
function group(multiple){return defineComponent({emits:['change'],setup(_, {slots,emit,attrs}){
 const values=new Set()
 const context={name:'sczx-choice-'+(++groupCount),register(value,checked){checked?values.add(value):values.delete(value)},remove(value){values.delete(value)},change(value,checked,e){
  if(multiple){checked?values.add(value):values.delete(value);emit('change',eventValue(e,[...values]))}
  else emit('change',eventValue(e,value))
 }}
 provide(groupKey,context)
 return()=>h('div',attrs,slots.default?.())
}})}
function choice(type){return defineComponent({inheritAttrs:false,props:{value:String,checked:Boolean,disabled:Boolean},setup(p,{attrs}){
 const group=inject(groupKey,null)
 onMounted(()=>group?.register(p.value,p.checked))
 watch(()=>[p.value,p.checked],([value,checked],[old])=>{if(old!==value)group?.remove(old);group?.register(value,checked)})
 onBeforeUnmount(()=>group?.remove(p.value))
 return()=>h('input',{...attrs,type,name:group?.name,value:p.value,checked:p.checked,disabled:p.disabled,onChange:e=>group?.change(p.value,e.target.checked,e)})
}})}
export const WebCheckboxGroup=group(true),WebRadioGroup=group(false),WebCheckbox=choice('checkbox'),WebRadio=choice('radio')
export const WebMovableArea=defineComponent({setup(_, {attrs,slots}){return()=>h('div',{...attrs,style:[{position:'relative',overflow:'hidden'},attrs.style]},slots.default?.())}})
export const WebMovable=defineComponent({inheritAttrs:false,props:{x:{type:Number,default:0},y:{type:Number,default:0},disabled:Boolean,direction:String},emits:['change'],setup(p,{attrs,slots,emit}){
 let start=null
 function move(e){if(!start||p.disabled||e.pointerId!==start.pointerId)return;emit('change',{detail:{source:'touch',x:Number((start.x+e.clientX-start.clientX).toFixed(1)),y:Number((start.y+e.clientY-start.clientY).toFixed(1))}})}
 function end(e){if(e&&start&&e.pointerId!==start.pointerId)return;start=null;window.removeEventListener('pointermove',move);window.removeEventListener('pointerup',end);window.removeEventListener('pointercancel',end)}
 onBeforeUnmount(end)
 watch(()=>p.disabled,disabled=>{if(disabled)end()})
 return()=>h('div',{...attrs,style:[{boxSizing:'content-box',display:'inline-block',width:'10px',height:'10px',cursor:'grab'},attrs.style,{position:'absolute',left:0,top:0,transform:`translate3d(${Number(p.x.toFixed(1))}px,${Number(p.y.toFixed(1))}px,0)`,touchAction:'none'}],onPointerdown:e=>{if(p.disabled||start||e.target!==e.currentTarget)return;e.preventDefault();start={pointerId:e.pointerId,x:p.x,y:p.y,clientX:e.clientX,clientY:e.clientY};window.addEventListener('pointermove',move);window.addEventListener('pointerup',end);window.addEventListener('pointercancel',end)}},slots.default?.())
}})
