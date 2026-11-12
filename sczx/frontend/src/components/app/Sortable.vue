<script setup>
import { ref } from 'vue';
import { ElTree } from 'element-plus';
const props=defineProps({modelValue:{type:Array,default:()=>[]},itemKey:{type:String,default:'id'},handle:String,disabled:Boolean}),emit=defineEmits(['update:modelValue','change','end']);
const armed=ref(false);let original=[],moved=null;
function arm(event){armed.value=!props.disabled&&(!props.handle||!!event.target.closest(props.handle))}
function begin(){original=[...props.modelValue];moved=null}
function drop(dragging,target,type){const key=props.itemKey,items=original.filter(item=>item[key]!==dragging.data[key]),index=items.findIndex(item=>item[key]===target.data[key]);if(index<0)return;const position=index+(type==='after'?1:0),element=original.find(item=>item[key]===dragging.data[key]);items.splice(position,0,element);moved={element,oldIndex:original.indexOf(element),newIndex:position};emit('update:modelValue',items);emit('change',{moved});emit('end',{...moved});original=[];moved=null}
function end(_dragging,target,type){armed.value=false;if(!target||type==='none'){original=[];moved=null}}
</script>
<template><ElTree :data="modelValue" :node-key="itemKey" :props="{children:'__noNestedItems'}" :draggable="!disabled" :allow-drag="()=>armed&&!disabled" :allow-drop="(_dragging,_target,type)=>!disabled&&type!=='inner'" :expand-on-click-node="false" :highlight-current="false" :indent="0" class="app-element-sortable" @mousedown.capture="arm" @node-drag-start="begin" @node-drop="drop" @node-drag-end="end"><template #default="{data}"><div class="sortable-item"><slot name="item" :element="data" :index="modelValue.findIndex(item=>item[itemKey]===data[itemKey])"/></div></template></ElTree></template>
