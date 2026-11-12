<script setup>
import { ref, watch } from "vue";
import { modelApi } from "@/services/models.js";
import ModelResult from "./ModelResult.vue";
const props = defineProps({ recordId: String });
const emit = defineEmits(['covered-helps']);
const items = ref([]), error = ref(''), loading = ref(false);
let displayedRecord;
async function load() {
  const id = props.recordId;
  if (displayedRecord !== id) { items.value = []; emit('covered-helps', []); displayedRecord = id; }
  if (!id) return;
  loading.value = true; error.value = '';
  try { const result = await modelApi.list(id); if (props.recordId === id) { items.value = result; emit('covered-helps', result.map(x => x.helpRecordId).filter(Boolean)); } }
  catch (problem) { if (props.recordId === id) { error.value = problem.message; emit('covered-helps', []); } }
  finally { if (props.recordId === id) loading.value = false; }
}
watch(() => props.recordId, load, { immediate: true });
</script>
<template><section class="model-learning-history"><div class="model-console-heading"><h3>提问记录</h3><AppButton variant="ghost" size="sm" @click="load">刷新</AppButton></div><p v-if="loading" role="status">读取中…</p><AppAlert type="error" v-if="error" role="alert" class="form-error">{{ error }}</AppAlert><p v-if="!loading && !items.length && !error" class="ai-empty">还没有提问</p><ModelResult v-for="item in items" :key="item.id" :job="item" :busy="['queued','running'].includes(item.status)" :can-retry="false" show-source /></section></template>
