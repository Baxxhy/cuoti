<script setup>
import { computed, onMounted, ref } from "vue";
import { RefreshCw, Play, FileAudio } from "@/components/app/icons.js";
import { capabilityNames, modelApi } from "@/services/models.js";
import { useModelJob } from "@/lib/useModelJob.js";
import ModelResult from "./ModelResult.vue";
import SpeechInput from "./SpeechInput.vue";
import SpeechReader from "./SpeechReader.vue";
const tabs = { text: '文字指导', ocr: '题图识别', retrieval: '案例检索', rerank: '材料重排', 'voice-input': '语音输入', 'read-aloud': '文字朗读' };
const rerank = ref(true);
const nativeVoice = computed(() => ['voice-input', 'read-aloud'].includes(selected.value));
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
  history.value = history.value.filter(x => !['document_parse','document_ocr','case_extract'].includes(x.capability));
}
async function run() {
  if (busy.value || uploading.value || activeConfig.value?.unavailableReason) return;
  loadError.value = '';
  const capability = selected.value;
  const data = capability === 'retrieval' ? { query: query.value, rerank: rerank.value } : capability === 'embedding' ? { texts: text.value.split(/\n+/).map(x => x.trim()).filter(Boolean) } : capability === 'rerank' ? { query: query.value, candidates: materials.value.split(/\n+/).filter(x => x.trim()).map((value, i) => ({ id: `材料${i + 1}`, text: value })) } : capability === 'tts' ? { text: text.value } : capability === 'text' ? { prompt: text.value } : {};
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
  selected.value = ({ embedding: 'retrieval', asr: 'voice-input', tts: 'read-aloud' })[item.capability] || item.capability;
  file.value = null;
  const input = job.value.input || {};
  if (item.capability === 'text') text.value = input.prompt || '';
  if (item.capability === 'tts') text.value = input.text || '';
  if (item.capability === 'asr') text.value = job.value.result?.correctedText || job.value.result?.text || '';
  if (item.capability === 'retrieval') { query.value = input.query || ''; rerank.value = !!input.rerank; }
  if (item.capability === 'embedding') text.value = (input.texts || []).join('\n');
  if (item.capability === 'rerank') { query.value = input.query || ''; materials.value = (input.candidates || []).map(x => x.text).join('\n'); }
}
function selectCapability(capability) { selected.value = capability; file.value = null; loadError.value = ''; open(null); }
onMounted(load);
async function saveCorrection() {
  correcting.value = true;
  try { await open(await modelApi.correct(job.value.id, transcript.value)); }
  catch (problem) { loadError.value = problem.message; }
  finally { correcting.value = false; }
}
</script>
<template>
  <div class="model-console-heading"><AppSelect :model-value="selected" label="验证能力" :options="Object.entries(tabs).map(([value,label])=>({value,label}))" @update:model-value="selectCapability"/><AppButton variant="ghost" size="icon-sm" aria-label="刷新模型与任务" @click="load"><RefreshCw :size="17" /></AppButton></div>

  <div class="model-console-grid">
    <div class="model-console-form">
      <template v-if="nativeVoice">

        <label class="field-label" for="browser-voice-text">{{ selected === 'voice-input' ? '输入文字' : '朗读文字' }}<InfoTip label="浏览器语音能力">使用浏览器与设备提供的语音服务；不支持时继续文字输入与阅读。朗读不生成音频文件。</InfoTip></label><Textarea id="browser-voice-text" v-model="text" class="model-input-large" />
        <div class="browser-voice-actions"><SpeechInput v-if="selected === 'voice-input'" :context-key="selected" @text="text = [text.trim(), $event].filter(Boolean).join(' ')" /><SpeechReader :text="text" /></div>
      </template>
      <template v-else>
      <div class="model-config-state"><Status :tone="activeConfig?.lastStatus==='failed'||!activeConfig?.configured ? 'amber' : 'green'">{{ activeConfig?.configured ? activeConfig.lastStatus === 'succeeded' ? '最近调用成功' : activeConfig.lastStatus === 'failed' ? '最近调用失败' : '已配置 　 待验证' : activeConfig?.unavailableReason ? '暂不可用' : '未配置' }}</Status><InfoTip v-if="activeConfig?.models?.length" label="模型配置">{{ activeConfig.models.map(x => `${x.model} 　 ${x.name}`).join(' / ') }}</InfoTip></div>
      <p v-if="activeConfig?.unavailableReason" role="status" class="model-model-name">{{ activeConfig.unavailableReason }}</p>

      <template v-if="['ocr', 'asr'].includes(selected)"><label class="field-label" for="model-input-file">{{ selected === 'ocr' ? '题目原图' : '音频文件' }}</label><label class="model-file-picker"><FileAudio v-if="selected === 'asr'" :size="20" /><span>{{ file?.name || '选择文件' }}</span><AppFilePicker id="model-input-file" :accept="selected === 'ocr' ? 'image/*' : 'audio/*'" @change="file = $event.target.files?.[0] || null"/></label></template>
      <template v-else-if="selected === 'retrieval'"><label class="field-label" for="retrieval-query">知识点或学生困难</label><Input id="retrieval-query" v-model="query" @keydown.enter="run" /><AppCheckbox class="retrieval-rerank" v-model="rerank">语义重排</AppCheckbox></template>
      <template v-else-if="selected === 'rerank'"><label class="field-label" for="rerank-query">教学问题</label><Input id="rerank-query" v-model="query" /><label class="field-label" for="rerank-materials">候选材料，每行一段</label><Textarea id="rerank-materials" v-model="materials" class="model-input-large" /></template>
      <template v-else><label class="field-label" for="model-input-text">{{ selected === 'embedding' ? '文本，每行一段' : selected === 'tts' ? '朗读文字' : '问题' }}</label><Textarea id="model-input-text" v-model="text" class="model-input-large" /></template>
      <AppButton class="model-run-button" :disabled="busy || uploading || !!activeConfig?.unavailableReason || !activeConfig" @click="run"><Play :size="15" />{{ uploading ? '上传中…' : busy ? '执行中…' : ({retrieval:'检索案例',text:'获取指导',ocr:'识别题图',rerank:'重排材料'})[selected]||'开始验证' }}</AppButton>
      </template>
      <AppAlert type="error" v-if="loadError || error" class="form-error" role="alert">{{ loadError || error }}</AppAlert>
      <ModelResult :job="job" :busy="busy" :can-retry="['text', 'ocr', 'retrieval', 'rerank'].includes(job?.capability)" show-source @retry="retry" />
      <template v-if="job?.capability === 'asr' && job.status === 'succeeded'"><label class="field-label" for="asr-correction">修订转写文字</label><Textarea id="asr-correction" v-model="transcript" /><div class="paper-actions"><AppButton variant="outline" :disabled="correcting" @click="saveCorrection">{{ correcting ? '保存中…' : '保存修订' }}</AppButton><AppButton variant="outline" @click="selected = 'read-aloud'; text = transcript">朗读修订文字</AppButton></div></template>
    </div>
    <details class="model-task-list ops-disclosure"><summary>最近任务 　 {{history.length}}</summary><p v-if="!history.length" class="ai-empty">暂无运行记录</p><button v-for="item in history" :key="item.id" :disabled="uploading || submitting" @click="selectJob(item)" :class="{ active: job?.id === item.id }"><div><strong>{{ capabilityNames[item.capability] }}</strong><span>{{ item.step }}</span></div><time>{{ new Date(item.createdAt).toLocaleString('zh-CN') }}</time></button></details>
  </div>
</template>
