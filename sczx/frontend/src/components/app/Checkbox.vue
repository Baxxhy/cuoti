<script setup>
import{computed}from'vue';import{ElCheckbox}from'element-plus';
defineOptions({inheritAttrs:false});const props=defineProps({modelValue:{default:undefined},checked:{default:undefined},value:{default:undefined}}),emit=defineEmits(['update:modelValue','change']);const checkedValue=computed(()=>Array.isArray(props.modelValue)?props.modelValue.includes(props.value):Boolean(props.modelValue??props.checked));function change(checked){const value=Array.isArray(props.modelValue)?checked?[...props.modelValue,props.value]:props.modelValue.filter(v=>v!==props.value):checked;emit('update:modelValue',value);emit('change',{target:{checked,value:props.value}})}
</script>
<template><ElCheckbox v-bind="$attrs" :model-value="checkedValue" @change="change"><slot/></ElCheckbox></template>
