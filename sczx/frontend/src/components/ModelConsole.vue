<script setup>
import { computed, onMounted, ref } from "vue";
import { RefreshCw, Play, FileAudio } from "lucide-vue-next";
import { capabilityNames, modelApi } from "@/services/models.js";
import { useModelJob } from "@/lib/useModelJob.js";
import ModelResult from "./ModelResult.vue";
const selected = ref('text'), configurations = ref([]), history = ref([]), loadError = ref('');
const text = ref('为什么等式两边要同时加上相同的数？'), query = ref('学生只改变等式一边，应该怎样引导？');
const materials = ref('用平衡天平引导学生观察两边同时增加相同砝码。\n让学生比较只改变左边与两边一起变化的结果。\n认识三角形内角和。');
const file = ref(null), uploading = ref(false), transcript = ref(''), correcting = ref(false);
const { job, busy, submitting, error, create, open, retry } = useModelJob(async (value) => {
  if (value.capability === 'asr' && value.status === 'succeeded') transcript.value = value.result.correctedText || value.result.text;
  await load();
});
const activeConfig = computed(() => configurations.value.find(item => item.capability === selected.value));
async function load() {
  loadError.value = '';
  try { [configurations.value, history.value] = await Promise.all([modelApi.capabilities(), modelApi.list()]); }
  catch (problem) { loadError.value = problem.message; }
}
async function run() {
  if (busy.value || uploading.value || activeConfig.value?.unavailableReason) return;
  loadError.value = '';
  const capability = selected.value;
  const data = capability === 'embedding' ? { texts: text.value.split(/\n+/).map(x => x.trim()).filter(Boolean) } : capability === 'rerank' ? { query: query.value, candidates: materials.value.split(/\n+/).filter(x => x.trim()).map((value, i) => ({ id: `材料${i + 1}`, text: value })) } : capability === 'tts' ? { text: text.value } : capability === 'text' ? { prompt: text.value } : {};
  let fileId;
  if (['ocr', 'asr'].includes(selected.value)) {
    if (!file.value) { loadError.value = '请先选择文件。'; return; }
    uploading.value = true;
    try { fileId = (await modelApi.upload(file.value)).id; }
    catch (problem) { loadError.value = problem.message; return; }
    finally { uploading.value = false; }
  }
  await create({ capability, fileId, data });
}
async function selectJob(item) {
  await open(item);
  if (job.value?.id !== item.id) return;
  selected.value = item.capability;
  file.value = null;
  const input = job.value.input || {};
  if (item.capability === 'text') text.value = input.prompt || '';
  if (item.capability === 'tts') text.value = input.text || '';
  if (item.capability === 'embedding') text.value = (input.texts || []).join('\n');
  if (item.capability === 'rerank') { query.value = input.query || ''; materials.value = (input.candidates || []).map(x => x.text).join('\n'); }
}
function selectCapability(capability) { selected.value = capability; file.value = null; loadError.value = ''; open(null); }
onMounted(async () => { await load(); if (history.value.length) await selectJob(history.value[0]); });
async function saveCorrection() {
  correcting.value = true;
  try { await open(await modelApi.correct(job.value.id, transcript.value)); }
  catch (problem) { loadError.value = problem.message; }
  finally { correcting.value = false; }
}
</script>
<template>
  <div class="model-console-heading"><SectionHeading title="模型与任务" /><Button variant="ghost" size="icon-sm" aria-label="刷新模型与任务" @click="load"><RefreshCw :size="17" /></Button></div>
  <div class="model-capability-tabs" role="group" aria-label="选择模型能力"><button v-for="(name, key) in capabilityNames" :key="key" :class="{ active: selected === key }" :disabled="uploading || submitting" @click="selectCapability(key)" :aria-pressed="selected === key">{{ name }}</button></div>
  <div class="model-console-grid">
    <div class="model-console-form">
      <div class="model-config-state"><h3>{{ capabilityNames[selected] }}</h3><Status :tone="activeConfig?.configured ? 'green' : 'amber'">{{ activeConfig?.configured ? activeConfig.lastStatus === 'succeeded' ? '最近调用成功' : activeConfig.lastStatus === 'failed' ? '最近调用失败' : '已配置 · 待验证' : activeConfig?.unavailableReason ? '暂不可用' : '未配置' }}</Status></div>
      <p v-if="activeConfig?.unavailableReason" role="status" class="model-model-name">{{ activeConfig.unavailableReason }}</p>
      <p v-if="activeConfig?.models?.length" class="model-model-name">{{ activeConfig.models.map(x => `${x.model} · ${x.name}`).join(' / ') }}</p>
      <template v-if="['ocr', 'asr'].includes(selected)"><label class="field-label" for="model-input-file">{{ selected === 'ocr' ? '题目原图' : '音频文件' }}</label><label class="model-file-picker"><FileAudio v-if="selected === 'asr'" :size="20" /><span>{{ file?.name || '选择文件' }}</span><input id="model-input-file" type="file" :accept="selected === 'ocr' ? 'image/*' : 'audio/*'" @change="file = $event.target.files?.[0] || null" /></label></template>
      <template v-else-if="selected === 'rerank'"><label class="field-label" for="rerank-query">教学问题</label><Input id="rerank-query" v-model="query" /><label class="field-label" for="rerank-materials">候选材料，每行一段</label><Textarea id="rerank-materials" v-model="materials" class="model-input-large" /></template>
      <template v-else><label class="field-label" for="model-input-text">{{ selected === 'embedding' ? '文本，每行一段' : selected === 'tts' ? '朗读文字' : '问题' }}</label><Textarea id="model-input-text" v-model="text" class="model-input-large" /></template>
      <Button class="model-run-button" :disabled="busy || uploading || !!activeConfig?.unavailableReason || !activeConfig" @click="run"><Play :size="15" />{{ uploading ? '上传中…' : busy ? '执行中…' : '运行验证' }}</Button>
      <p v-if="loadError || error" class="form-error" role="alert">{{ loadError || error }}</p>
      <ModelResult :job="job" :busy="busy" show-source @retry="retry" />
      <template v-if="job?.capability === 'asr' && job.status === 'succeeded'"><label class="field-label" for="asr-correction">修订转写文字</label><Textarea id="asr-correction" v-model="transcript" /><div class="paper-actions"><Button variant="outline" :disabled="correcting" @click="saveCorrection">{{ correcting ? '保存中…' : '保存修订' }}</Button><Button variant="outline" @click="selected = 'tts'; text = transcript">用于生成讲解音频</Button></div></template>
    </div>
    <div class="model-task-list"><h3>最近任务</h3><p v-if="!history.length" class="ai-empty">暂无运行记录</p><button v-for="item in history" :key="item.id" :disabled="uploading || submitting" @click="selectJob(item)" :class="{ active: job?.id === item.id }"><div><strong>{{ capabilityNames[item.capability] }}</strong><span>{{ item.step }}</span></div><time>{{ new Date(item.createdAt).toLocaleString('zh-CN') }}</time></button></div>
  </div>
</template>
