<script setup>
import { ref, computed, onMounted, onUpdated, watch, useAttrs } from 'vue';
import { ElInput, ElInputNumber, ElDatePicker } from 'element-plus';
defineOptions({inheritAttrs:false});
const props=defineProps({modelValue:[String,Number],defaultValue:[String,Number]}),emit=defineEmits(['update:modelValue']),attrs=useAttrs();
const local=ref(props.modelValue??props.defaultValue??''),control=ref(),host=ref();
const kind=computed(()=>attrs.type),forwarded=computed(()=>{const value=Object.fromEntries(Object.entries(attrs).filter(([key])=>key!=='type'));for(const key of ['min','max','step','precision'])if(value[key]!==undefined&&kind.value==='number')value[key]=Number(value[key]);return value});
const numeric=computed({get:()=>local.value===''||local.value===null?undefined:Number(local.value),set:update});
watch(()=>props.modelValue,value=>{if(value!==undefined)local.value=value});
function update(value){local.value=value;emit('update:modelValue',value)}
function syncNative(){const input=host.value?.querySelector('input');if(!input)return;input.setAttribute('data-slot','input');if(attrs.id){input.id=attrs.id;for(const node of host.value.querySelectorAll('[id]'))if(node!==input&&node.id===attrs.id)node.removeAttribute('id')}if(attrs['aria-label'])input.setAttribute('aria-label',attrs['aria-label']);if(attrs.required!==undefined)input.required=attrs.required!==false}
onMounted(syncNative);onUpdated(syncNative);
</script>
<template><span ref="host" class="element-input-host"><ElInputNumber v-if="kind==='number'" ref="control" v-bind="forwarded" v-model="numeric" controls-position="right" class="app-element-input"/><ElDatePicker v-else-if="kind==='date'||kind==='datetime-local'" ref="control" v-bind="forwarded" :type="kind==='date'?'date':'datetime'" :value-format="kind==='date'?'YYYY-MM-DD':'YYYY-MM-DDTHH:mm'" :format="kind==='date'?'YYYY-MM-DD':'YYYY-MM-DD HH:mm'" :model-value="local" @update:model-value="update" class="app-element-input"/><ElInput v-else ref="control" v-bind="forwarded" :type="kind||'text'" :model-value="local" @update:model-value="update" class="app-element-input"/></span></template>
