<script setup>
import{computed,useAttrs}from'vue';import{ElAlert}from'element-plus';defineOptions({inheritAttrs:false});const props=defineProps({type:String}),attrs=useAttrs();const kind=computed(()=>props.type||({pending:'warning',active:'info',danger:'error',success:'success'})[attrs['data-status']]||'info');
</script>
<template><ElAlert v-bind="attrs" :type="kind" :closable="false" show-icon :role="kind==='error'?'alert':'status'"><slot/></ElAlert></template>
