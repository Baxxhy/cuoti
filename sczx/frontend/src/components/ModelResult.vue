<script setup>
import { computed, ref, watch } from "vue";
import { LoaderCircle, RotateCcw, Check, CircleAlert } from "lucide-vue-next";
import SpeechReader from "./SpeechReader.vue";
import { capabilityNames } from "@/services/models.js";
const props = defineProps({ job: Object, busy: Boolean, showSource: Boolean, canRetry: { type: Boolean, default: true } });
defineEmits(["retry"]);
const expanded = ref(false);
const uniqueReferences = refs => [...new Map((refs || []).map(item => [item.unitId, item])).values()];
watch(() => props.job?.id, () => { expanded.value = false; });
const result = computed(() => props.job?.result);
const verification = computed(() => ({ verified: "列出的等式已核对", inconsistent: "发现数学不一致", unverified: "数学需核对" })[result.value?.verification?.status]);
</script>
<template>
  <section v-if="job" class="model-result" :aria-busy="busy">
    <div class="model-status" role="status" aria-live="polite">
      <LoaderCircle v-if="busy" :size="17" class="model-spinner" />
      <CircleAlert v-else-if="job.status === 'failed'" :size="17" />
      <Check v-else :size="17" />
      <strong>{{ capabilityNames[job.capability] }}</strong><span>{{ job.step }}</span>
    </div>
    <div v-if="job.error" class="model-error" role="alert">{{ job.error }}</div>
    <Button v-if="canRetry && job.status === 'failed'" variant="outline" :disabled="busy" @click="$emit('retry')"><RotateCcw :size="16" />重试</Button>
    <img v-if="showSource && job.fileId && ['text', 'ocr'].includes(job.capability)" :src="`/api/files/${job.fileId}`" class="ai-original" alt="原始题图" />
    <audio v-if="showSource && job.fileId && job.capability === 'asr'" :src="`/api/files/${job.fileId}`" class="model-audio" controls aria-label="转写原始音频" />
    <template v-if="result && job.status === 'succeeded'">
      <details v-if="job.recognizedText" class="model-run-history"><summary>学生确认的题目</summary><p class="model-prose">{{ job.recognizedText }}</p></details>
      <template v-if="job.capability === 'text'">
        <SpeechReader :text="[result.title, result.hint, ...(expanded ? result.steps || [] : [])].filter(Boolean).join('。')" />
        <h3>{{ result.title }}</h3><p class="model-prose">{{ result.hint }}</p>
        <Button variant="outline" @click="expanded = !expanded" :aria-expanded="expanded">{{ expanded ? '收起讲解' : '展开分步讲解' }}</Button>
        <ol v-if="expanded" class="model-steps"><li v-for="(step, index) in result.steps" :key="index">{{ step }}</li></ol>
        <p v-if="result.question" class="model-followup">{{ result.question }}</p>
        <div class="model-verification"><Status :tone="result.verification?.status === 'verified' ? 'green' : 'amber'">{{ verification }}</Status><InfoTip label="数学核对范围">{{ result.verification?.scope }}</InfoTip></div>
      </template>
      <p v-else-if="result.text" class="model-prose">{{ result.text }}</p>
      <p v-if="result.equation" class="model-prose">{{ result.equation }}</p>
      <p v-if="result.studentAnswer" class="model-prose">原作答：{{ result.studentAnswer }}</p>
      <div v-if="result.uncertainties?.length" class="model-error">待核对：{{ result.uncertainties.join('；') }}</div>
      <div v-if="job.capability === 'embedding'" class="model-metrics"><div><strong>{{ result.count }}</strong><span>段文本</span></div><div><strong>{{ result.dimensions }}</strong><span>向量维度</span></div></div>
      <div v-if="job.capability === 'retrieval'" class="retrieval-results">
        <p v-if="!result.items?.length" class="ai-empty">没有匹配的案例，换个知识点或学生困难试试。</p>
        <p v-if="result.warning" role="status" class="model-model-name">{{ result.warning }}</p>
        <details v-for="item in result.items" :key="item.id" class="retrieval-item"><summary>{{ item.title }}</summary><p class="model-prose">{{ item.content }}</p><span class="model-model-name">{{ item.source || '团队编写案例示例' }}</span></details>
        <InfoTip v-if="result.items?.length" label="检索方式">BM25 中文检索{{ result.rerankApplied ? '，已完成 Codex 语义重排' : '' }}；相关分值不代表内容正确性。</InfoTip>
      </div>
      <details v-if="result.sources?.length" class="model-run-history"><summary>参考教学案例 · {{ result.sources.length }}</summary><section v-for="source in result.sources" :key="`${source.id}:${source.versionId||''}`"><p>{{ source.role === 'lesson' ? '课时关联 · ' : '' }}{{ source.title }}{{ source.version ? ' · v'+source.version : '' }}</p><a v-for="(ref,index) in uniqueReferences(source.references)" :key="index" :href="`/#/source?unit=${ref.unitId}`" target="_blank" rel="noopener">{{ ref.materialTitle }} · {{ ref.label }}</a></section></details>
      <ol v-if="result.ranking" class="model-ranking"><li v-for="item in result.ranking" :key="item.id"><strong>{{ item.id }}</strong><span>{{ item.score }}</span></li></ol>
      <InfoTip v-if="result.scoreMeaning" label="重排方法与分值">{{ result.method === 'llm' ? 'LLM 语义重排。' : '' }}{{ result.scoreMeaning }}</InfoTip>
      <audio v-if="result.url" class="model-audio" controls :src="result.url" aria-label="生成的讲解音频" preload="metadata" />
    </template>
    <details v-if="job.runs?.length" class="model-run-history"><summary>执行记录 · {{ job.runs.length }}</summary><div v-for="run in job.runs" :key="run.id"><span>第 {{ run.number }} 次 · {{ { running: '执行中', succeeded: '成功', failed: '失败' }[run.status] }}</span><span>{{ run.model }}</span><p v-if="run.error">{{ run.error }}</p></div></details>
  </section>
</template>
