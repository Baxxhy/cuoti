<script setup>
import { computed, ref, watch } from "vue";
import { ImagePlus, Send, Sparkles } from "lucide-vue-next";
import { useLearning } from "@/store.js";
import { modelApi } from "@/services/models.js";
import { useModelJob } from "@/lib/useModelJob.js";
import ModelResult from "./ModelResult.vue";
import SpeechInput from "./SpeechInput.vue";
const props = defineProps({ question: { default: null }, compact: Boolean });
const emit = defineEmits(["help"]);
const store = useLearning();
const recordId = computed(() => store.record?.id);
const prompt = ref(""), file = ref(null), uploading = ref(false), uploadError = ref(""), recognized = ref("");
const ocrId = ref(null), originalFileId = ref(null);
const draftKey = computed(() => props.question === null ? 'assistant' : `assistantQuestion-${props.question}`);
const { job, busy, error, create, open, retry } = useModelJob(async (value) => {
  if (value.status === 'succeeded' && value.capability === 'ocr') { recognized.value = store.record?.drafts[`ocr-${value.id}`] || [value.result.text, value.result.equation && !value.result.text.includes(value.result.equation) ? value.result.equation : '', value.result.studentAnswer ? `原作答：${value.result.studentAnswer}` : ''].filter(Boolean).join('\n'); ocrId.value = value.id; originalFileId.value = value.fileId; }
  if (value.status === 'succeeded' && value.capability === 'text' && recordId.value === value.recordId) await store.refreshRecord();
});
watch(recordId, async (id, _, onCleanup) => {
  let live = true;
  onCleanup(() => { live = false; });
  await open(null); ocrId.value = null; originalFileId.value = null; recognized.value = ""; file.value = null;
  prompt.value = store.record?.drafts[draftKey.value] || '';
  if (!id) return;
  try {
    const jobs = await modelApi.list(id);
    const latest = jobs.find((item) => ['text','ocr'].includes(item.capability) && (item.question ?? null) === props.question);
    if (live && latest) { await open(latest); if (!prompt.value) prompt.value = job.value?.input?.prompt || ''; }
  } catch (problem) { if (live) uploadError.value = problem.message; }
}, { immediate: true });
watch(prompt, (value) => { if (store.record) { store.record.drafts[draftKey.value] = value; store.touch(); } });
watch(recognized, (value) => { if (store.record && ocrId.value) { store.record.drafts[`ocr-${ocrId.value}`] = value; store.touch(); } });
async function send() {
  if (busy.value || uploading.value) return;
  uploadError.value = "";
  const targetRecord = recordId.value, targetQuestion = props.question, originalPrompt = prompt.value;
  if (file.value) {
    uploading.value = true;
    try {
      const asset = await modelApi.upload(file.value);
      originalFileId.value = asset.id;
      file.value = null;
      await create({ capability: 'ocr', recordId: targetRecord, fileId: asset.id, data: { question: targetQuestion, prompt: originalPrompt } });
    } catch (problem) { uploadError.value = problem.message; }
    finally { uploading.value = false; }
    return;
  }
  if (job.value?.capability === 'ocr' && job.value.status === 'succeeded') return confirmOCR();
  if (!prompt.value.trim()) { uploadError.value = "先写下问题或选择题图。"; return; }
  emit('help');
  if (!(await store.save())) { uploadError.value = store.saveError; return; }
  await create({ capability: 'text', recordId: targetRecord, data: { prompt: originalPrompt, question: targetQuestion } });
}
async function confirmOCR() {
  if (!recognized.value.trim()) { uploadError.value = "请核对识别的题目。"; return; }
  const targetRecord = recordId.value, targetQuestion = props.question;
  const data = { prompt: prompt.value.trim() || '请引导我理解这道题，先给提示。', question: targetQuestion, ocrJobId: ocrId.value, confirmed: true, recognizedText: recognized.value };
  const fileId = originalFileId.value;
  emit('help');
  if (!(await store.save())) { uploadError.value = store.saveError; return; }
  await create({ capability: 'text', recordId: targetRecord, fileId, data });
}
</script>
<template>
  <aside class="ai-assistant" :class="{ 'is-compact': compact }">
    <div class="ai-assistant-heading"><Sparkles :size="19" /><h3>学习助手</h3></div>
    <p v-if="!job" class="ai-empty">你想从哪里开始理解？</p>
    <ModelResult :job="job" :busy="busy" :show-source="job?.status === 'failed'" @retry="retry" />
    <template v-if="job?.capability === 'ocr' && job.status === 'succeeded' && ocrId === job.id">
      <img :src="`/api/files/${job.fileId}`" class="ai-original" alt="识别所用原始题图" />
      <label class="field-label" for="confirmed-question">核对题目</label><Textarea id="confirmed-question" v-model="recognized" :disabled="busy" />
      <Button @click="confirmOCR" :disabled="busy">确认题目并获取提示</Button>
    </template>
    <div class="ai-compose">
      <label class="sr-only" for="learning-question">向学习助手提问</label><Textarea id="learning-question" v-model="prompt" placeholder="写下还没想明白的地方…" />
      <div class="ai-compose-actions"><SpeechInput :context-key="`${recordId}:${question}`" :disabled="busy || uploading" @text="prompt = [prompt.trim(), $event].filter(Boolean).join(' ' )" /><label class="image-input"><ImagePlus :size="18" /><span class="sr-only">选择题图</span><input type="file" accept="image/*" :disabled="busy || uploading" @change="file = $event.target.files?.[0] || null; ocrId = null" /></label><span class="ai-file-name">{{ file?.name || '题图' }}</span><Button :disabled="busy || uploading || !recordId" @click="send"><Send :size="16" />{{ uploading ? '上传中…' : busy ? '处理中…' : file ? '识别题图' : '发送' }}</Button></div>
    </div>
    <p v-if="uploadError || error" class="form-error" role="alert">{{ uploadError || error }}</p>
  </aside>
</template>
