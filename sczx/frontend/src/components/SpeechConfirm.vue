<script setup>
import {ref,watch} from 'vue';import SpeechInput from './SpeechInput.vue';
const props=defineProps({contextKey:[String,Number],disabled:Boolean});const emit=defineEmits(['confirmed']);const recognized=ref(''),open=ref(false);watch(()=>props.contextKey,()=>{recognized.value='';open.value=false});
</script>
<template><SpeechInput :context-key="contextKey" :disabled="disabled" @text="text=>{recognized=text;open=true}"/><AppDialog v-model:open="open" title="核对语音文字"><label>识别内容<Textarea v-model="recognized" aria-label="核对语音文字"/></label><p>请核对数字、运算符和非零条件。</p><AppButton :disabled="!recognized.trim()" @click="emit('confirmed',recognized);open=false">确认填入</AppButton></AppDialog></template>
