<script setup>
import {ref,onMounted,onUpdated,watch} from 'vue';
import {ElInput} from 'element-plus';
defineOptions({inheritAttrs:false});
const props=defineProps({modelValue:[String,Number],defaultValue:[String,Number]}),emit=defineEmits(['update:modelValue']);
const local=ref(props.modelValue??props.defaultValue??''),control=ref();
watch(()=>props.modelValue,value=>{if(value!==undefined)local.value=value});
function update(value){local.value=value;emit('update:modelValue',value)}
function syncNative(){control.value?.input?.setAttribute('data-slot','input');control.value?.$el?.removeAttribute('aria-label')}
onMounted(syncNative);onUpdated(syncNative);
</script>
<template><ElInput ref="control" class="app-element-input" v-bind="$attrs" :model-value="local" @update:model-value="update"/></template>
