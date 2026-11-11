<script setup>
import {ref,onMounted} from 'vue';import {api} from '@/services/api.js';import {modelApi,capabilityNames} from '@/services/models.js';
const rows=ref([]),error=ref(''),busy=ref(false);
async function load(){try{rows.value=await api.request('/ai/failures');error.value=''}catch(e){error.value=e.message}}
async function retry(r){if(busy.value)return;busy.value=true;try{await modelApi.retry(r.id);await load()}catch(e){error.value=e.message}finally{busy.value=false}}
onMounted(load);
</script>
<template><SectionHeading title="失败任务"><Button variant="outline" @click="load">刷新</Button></SectionHeading><p v-if="error" class="form-error" role="alert">{{error}}</p><div class="analytics-queue"><article v-for="r in rows" :key="r.id"><div><strong>{{capabilityNames[r.capability]||'后台任务'}}</strong><InfoTip label="任务详情">{{new Date(r.createdAt).toLocaleString('zh-CN')}} · {{r.attemptNumber}} 次执行 · {{r.retryCount}} 次自动重试</InfoTip><p>{{r.error}}</p><p v-if="r.retryBlockedReason">{{r.retryBlockedReason}}</p></div><Button :disabled="busy||!r.canRetry" variant="outline" @click="retry(r)">重试</Button></article><p v-if="!rows.length" class="empty-state">暂无失败任务</p></div></template>
