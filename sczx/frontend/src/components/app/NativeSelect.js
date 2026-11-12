import {defineComponent,h} from 'vue';
import {ElSelect,ElOption} from 'element-plus';
import {statusText} from '@/lib/status-tone.js';
function options(nodes){return (Array.isArray(nodes)?nodes:[nodes]).flatMap(node=>node?.type==='option'?[{value:node.props?.value??statusText(node.children),label:statusText(node.children),disabled:node.props?.disabled!==undefined&&node.props.disabled!==false}]:Array.isArray(node?.children)?options(node.children):[])}
export default defineComponent({inheritAttrs:false,props:{modelValue:[String,Number,Array]},emits:['update:modelValue','change'],setup(props,{attrs,slots,emit}){return()=>h(ElSelect,{...attrs,modelValue:props.modelValue,multiple:attrs.multiple!==undefined&&attrs.multiple!==false,class:['app-element-select',attrs.class],'onUpdate:modelValue':v=>emit('update:modelValue',v),onChange:v=>emit('change',{target:{value:v}})},()=>options(slots.default?.()||[]).map(option=>h(ElOption,option)))}});
