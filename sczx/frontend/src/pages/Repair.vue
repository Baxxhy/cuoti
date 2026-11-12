<script setup>
import AnswerInput from "@/components/AnswerInput.vue";
import MathExpression from "@/components/MathExpression.vue";
import MemoryReturn from "@/components/MemoryReturn.vue";
import { computed, ref, watch, onBeforeUnmount } from "vue";
import { useRoute } from "vue-router";
import {
  ArrowLeft,
  ArrowUpRight,
  CheckCircle2,
  RefreshCw,
  Send,
  ChevronRight,
} from "@/components/app/icons.js";
import { wrongApi, wrongStatuses } from "@/services/wrongs.js";
import { modelApi } from "@/services/models.js";
import { useModelJob } from "@/lib/useModelJob.js";
import { navigate } from "@/lib/navigation.js";
const route = useRoute(),
  wrong = ref(null),
  options = ref({ reasons: [], knowledge: [] }),
  loading = ref(true),
  error = ref(""),
  saving = ref(false),
  response = ref(""),
  answer = ref(""),
  reason = ref(""),
  cause = ref("其他或待确认"),
  confirmed = ref(false),
  lastAttempt = ref(null),
  assistantOpen = ref(false), originalOpen=ref(false), phase=ref("analysis"), correctionIndex=ref(0);
const strategies = [
  ["hint", "给我提示"],
  ["example", "举个例子"],
  ["rephrase", "换种讲法"],
  ["foundation", "补基础"],
];
let version = 0,
  timer,
  requestKeys = {},
  disposed = false;
const job = useModelJob(async (value) => {
  if (value.status === "succeeded") await load(false);
});
const jobs = computed(() => wrong.value?.jobs || []);
const analysis = computed(() =>
  [...jobs.value]
    .reverse()
    .find((j) => j.input.mode === "analysis" && j.status === "succeeded"),
);
const variant = computed(() =>
  [...jobs.value]
    .reverse()
    .find(
      (j) =>
        j.input.mode === "variant" &&
        j.status === "succeeded" &&
        !wrong.value.repairs.some((a) => a.details.variantJobId === j.id),
    ),
);
const helpTarget = computed(()=>phase.value==='practice'?variant.value?.id||null:null);
const parent = computed(() =>
  [...jobs.value]
    .reverse()
    .find(
      (j) =>
        ["analysis", "guidance"].includes(j.input.mode) &&
        j.status === "succeeded" &&
        (j.input.variantJobId||null)===helpTarget.value,
    ),
);
const guidance = computed(() =>
  jobs.value.filter((j) => j.input.mode === "guidance" && (j.input.variantJobId||null)===helpTarget.value),
);
const repairStatus=computed(()=>({pending:'待订正',learning:'订正中',awaiting_retest:'再试一题',retest_passed:'已复测',retest_failed:'继续订正',needs_review:'需核对'})[wrong.value?.status]||wrongStatuses[wrong.value?.status]);
const correctionStep=computed(()=>analysis.value?.result.steps?.[correctionIndex.value]||'');
watch(()=>[wrong.value?.id,analysis.value?.id,variant.value?.id,lastAttempt.value?.id],([id,a,v,last],[oldId,oldA,oldV,oldLast]=[])=>{
 if(id!==oldId){phase.value=v?'practice':last?'result':'analysis';correctionIndex.value=0;originalOpen.value=assistantOpen.value=false;}
 else if(v&&v!==oldV){phase.value='practice';assistantOpen.value=false;response.value='';}
 else if(last&&last!==oldLast) phase.value='result';
 else if(a&&a!==oldA){phase.value='analysis';correctionIndex.value=0;}
});
const knowledgeNames = computed(() =>
  options.value.knowledge
    .filter((p) => wrong.value?.details.knowledgeIds?.includes(p.id))
    .map((p) => p.name)
    .join(" 　 "),
);
async function load(initial = true) {
  const id = String(route.query.wrong || ""),
    token = version;
  if (initial) loading.value = true;
  error.value = "";
  try {
    const [item, opts] = await Promise.all([
      wrongApi.detail(id),
      wrongApi.options(),
    ]);
    if (disposed || token !== version) return;
    wrong.value = item;
    options.value = opts;
    if (initial) {
      const d = item.details.draft || {};
      const sameVariant = d.variantJobId === variant.value?.id;
      answer.value = sameVariant ? d.answer || "" : "";
      reason.value = sameVariant ? d.reason || "" : "";
      response.value = d.response || "";
      cause.value = item.details.cause || "其他或待确认";
      confirmed.value = item.details.causeConfirmed === true;
      lastAttempt.value = item.repairs.at(-1) || null;
      const pending = item.jobs.find((j) =>
        ["queued", "running"].includes(j.status),
      );
      const latest = item.jobs.at(-1);
      if (pending || latest?.status === "failed")
        await job.open(pending || latest);
    }
  } catch (e) {
    if (token === version) error.value = e.message;
  } finally {
    if (token === version) loading.value = false;
  }
}
watch(
  () => route.query.wrong,
  async () => {
    version++;
    clearTimeout(timer);
    wrong.value = null;
    requestKeys = {};
    lastAttempt.value = null;
    await job.open(null);
    load();
  },
  { immediate: true },
);
function schedule() {
  clearTimeout(timer);
  if (!wrong.value || wrong.value.readOnly) return;
  const id = wrong.value.id,
    token = version;
  timer = setTimeout(async () => {
    try {
      await wrongApi.save(id, {
        cause: cause.value,
        causeConfirmed: confirmed.value,
        draft: {
          variantJobId: variant.value?.id || null,
          answer: answer.value,
          reason: reason.value,
          response: response.value,
        },
      });
    } catch (e) {
      if (token === version) error.value = e.message;
    }
  }, 650);
}
watch([answer, reason, response], schedule);
async function confirmCause() {
  saving.value = true;
  try {
    await wrongApi.save(wrong.value.id, {
      cause: cause.value,
      causeConfirmed: confirmed.value,
      draft: {
        variantJobId: variant.value?.id || null,
        answer: answer.value,
        reason: reason.value,
        response: response.value,
      },
    });
    await load(false);
  } catch (e) {
    error.value = e.message;
  } finally {
    saving.value = false;
  }
}
async function create(mode, strategy = "hint", phase = "practice") {
  if (!wrong.value || wrong.value.readOnly || job.busy.value) return;
  if(mode==='guidance')assistantOpen.value=true;
  const data = {
    wrongId: wrong.value.id,
    mode,
    strategy,
    phase,
    prompt: mode === "guidance" ? response.value : "",
    parentJobId: mode === "guidance" ? parent.value?.id : null,
    ...(mode==='guidance'&&helpTarget.value?{variantJobId:helpTarget.value}:{}),
  };
  const key = JSON.stringify(data);
  requestKeys[key] ||= crypto.randomUUID();
  await job.create({
    capability: "text",
    recordId: wrong.value.recordId || null,
    requestKey: requestKeys[key],
    data,
  });
  if (!job.error.value) {
    delete requestKeys[key];
    if (mode === "variant") {
      answer.value = "";
      reason.value = "";
      lastAttempt.value = null;
    }
  }
}
async function submit() {
  if (saving.value || !variant.value) return;
  saving.value = true;
  error.value = "";
  const id = wrong.value.id,
    token = version,
    payload = {
      variantJobId: variant.value.id,
      answer: answer.value,
      reason: reason.value,
    };
  const k = JSON.stringify(payload);
  requestKeys[k] ||= crypto.randomUUID();
  try {
    const result = await wrongApi.attempt(id, {
      ...payload,
      requestKey: requestKeys[k],
    });
    if (token !== version) return;
    lastAttempt.value = result;
    delete requestKeys[k];
    await load(false);
  } catch (e) {
    if (token === version) error.value = e.message;
  } finally {
    if (token === version) saving.value = false;
  }
}
async function stop() {
  try {
    await modelApi.stop(job.job.value.id);
    await job.open({ id: job.job.value.id });
    await load(false);
  } catch (e) {
    error.value = e.message;
  }
}
onBeforeUnmount(() => {
  disposed = true;
  version++;
  clearTimeout(timer);
});
</script>
<template>
  <MemoryReturn/>
  <ElSkeleton v-if="loading" animated :rows="3" aria-label="正在读取错题…"/>
  <Surface v-else-if="error&&!wrong"><h2>无法打开错题</h2><AppAlert type="error" role="alert">{{error}}</AppAlert><AppButton @click="load()">重新读取</AppButton></Surface>
  <template v-else-if="wrong">
    <PageHeading title="错题订正"><AppButton variant="ghost" @click="navigate('wrong')"><ArrowLeft :size="16"/>我的错题</AppButton></PageHeading>
    <AppAlert  v-if="wrong.readOnly" role="status" class="inline-notice" data-status="neutral">此任务已转为历史记录，仅可回看。</AppAlert>
    <div class="remediation-workspace student-repair-focus">
      <aside class="remediation-original">
        <div><span class="student-original-label">原题</span><h2>{{wrong.prompt}}</h2></div>
        <AppButton variant="outline" @click="originalOpen=true">原来的作答<ChevronRight :size="15"/></AppButton>
      </aside>
      <nav class="student-repair-path" aria-label="错题订正步骤"><button :class="{active:phase==='analysis'}" :aria-current="phase==='analysis'?'step':undefined" @click="phase='analysis'"><span>1</span>找错因</button><button :disabled="!analysis" :class="{active:phase==='understand'}" :aria-current="phase==='understand'?'step':undefined" @click="phase='understand'"><span>2</span>订正</button><button :disabled="!variant&&!lastAttempt" :class="{active:['practice','result'].includes(phase)}" :aria-current="['practice','result'].includes(phase)?'step':undefined" @click="phase=variant?'practice':'result'"><span>3</span>再练一题</button></nav>
      <main class="remediation-main">
        <AppAlert  v-if="job.busy.value" class="inline-notice" data-status="active" role="status"><RefreshCw class="animate-spin" :size="16"/>{{job.job.value?.step||'正在准备…'}}<AppButton v-if="job.job.value?.input?.guidance" size="sm" variant="ghost" @click="stop">停止</AppButton></AppAlert>
        <AppAlert type="error" v-if="job.error.value||job.job.value?.status==='failed'" class="form-error" role="alert">{{job.error.value||job.job.value.error}}<AppButton :disabled="job.busy.value||wrong.readOnly" variant="outline" @click="job.job.value?.status==='failed'?job.retry():load(false)">重试</AppButton></AppAlert>
        <section v-if="phase==='analysis'" class="remediation-section student-repair-analysis">
          <template v-if="analysis"><h2>{{analysis.result.goal}}</h2><blockquote v-if="analysis.result.evidence">{{analysis.result.evidence}}</blockquote><div class="student-cause-answer"><span>这次先看</span><strong>{{analysis.result.cause}}</strong><InfoTip v-if="analysis.result.uncertainty" label="分析说明">{{analysis.result.uncertainty}}</InfoTip></div><AppButton @click="phase='understand'">开始订正<ChevronRight :size="16"/></AppButton><AppButton variant="ghost" :disabled="wrong.readOnly||job.busy.value" @click="create('analysis')">重新分析</AppButton></template>
          <template v-else><h2>先看看错在哪里</h2><p class="student-original-inline">你的答案 <strong>{{wrong.answer||'未填写'}}</strong></p><AppButton :disabled="wrong.readOnly||job.busy.value" @click="create('analysis')">分析这道题<ChevronRight :size="16"/></AppButton></template>
        </section>
        <section v-if="phase==='understand'&&analysis" class="remediation-section student-repair-correction"><div class="student-correction-counter">{{correctionIndex+1}} / {{analysis.result.steps.length}}</div><h2>一步步订正</h2><p class="student-correction-step">{{correctionStep}}</p><div v-if="correctionIndex<analysis.result.steps.length-1" class="student-correction-navigation"><AppButton variant="ghost" :disabled="correctionIndex===0" @click="correctionIndex--">上一步</AppButton><AppButton @click="correctionIndex++">下一步<ChevronRight :size="16"/></AppButton></div><template v-else><p class="remediation-question">{{analysis.result.checkQuestion}}</p><label class="field-label" for="repair-response">写下你的想法</label><Textarea id="repair-response" v-model="response" :disabled="wrong.readOnly"/><div class="paper-actions"><AppButton :disabled="wrong.readOnly||job.busy.value" @click="create('variant')">练一道类似的题<ChevronRight :size="16"/></AppButton><AppButton variant="ghost" :disabled="wrong.readOnly||job.busy.value||!response.trim()" @click="create('guidance','continue')">请帮我看看</AppButton><AppButton variant="ghost" :disabled="correctionIndex===0" @click="correctionIndex--">上一步</AppButton></div></template></section>
        <section v-if="phase==='practice'&&variant" class="remediation-section student-repair-practice"><span class="student-correction-counter">{{variant.input.phase==='retest'?'独立练习':'类似的题'}}</span><h2>{{variant.result.variant.prompt}}</h2><div v-if="variant.result.variant.equation" class="question-equation"><MathExpression :text="variant.result.variant.equation"/></div><form @submit.prevent="submit"><label class="field-label" for="repair-answer">你的答案</label><AnswerInput :question="variant.result.variant" id="repair-answer" v-model="answer" :disabled="wrong.readOnly||saving" required/><label class="field-label" for="repair-reason">思路与依据</label><Textarea id="repair-reason" v-model="reason" :disabled="wrong.readOnly||saving"/><AppButton type="submit" :disabled="wrong.readOnly||saving||!answer.trim()">{{saving?'正在保存…':'提交答案'}}</AppButton></form></section>
        <section v-if="phase==='result'&&lastAttempt" class="remediation-section repair-outcome"><CheckCircle2/><h2>{{lastAttempt.verification?.status==='unverified'?'请老师核对一下':lastAttempt.correct?'答案已核对':'再检查一下'}}</h2><p class="math-equation">{{lastAttempt.details.equation}} → {{lastAttempt.answer}}</p><p v-if="lastAttempt.details.helped">这次用过帮助</p><p v-if="lastAttempt.details.version==='legacy_fixed'">{{lastAttempt.details.scope}}</p><div class="paper-actions"><AppButton :disabled="wrong.readOnly||job.busy.value" @click="create('variant','hint','retest')">独立再试一题</AppButton><AppButton variant="outline" @click="navigate(wrong.taskId?'result?task='+wrong.taskId:'wrong')">{{wrong.taskId?'返回本课':'返回我的错题'}}</AppButton></div></section>
        <div class="student-repair-help"><AppButton variant="ghost" @click="assistantOpen=true">需要一点提示</AppButton><Status :tone="wrong.status==='retest_passed'?'green':'neutral'">{{repairStatus}}</Status></div>
      </main>
    </div>
    <AppAlert type="error" v-if="error" role="alert" class="form-error">{{error}}<AppButton variant="outline" :disabled="saving" @click="confirmCause">重试保存</AppButton></AppAlert>
    <AppDialog v-model:open="originalOpen" title="原题与作答" content-class="student-original-dialog"><h2>{{wrong.prompt}}</h2><a v-if="wrong.image" :href="wrong.image" target="_blank" rel="noreferrer"><AppImage class="wrong-detail-image" :src="wrong.image" alt="原始题图"/></a><AppImage v-if="wrong.details.cropFileId" class="wrong-detail-image" :src="'/api/files/'+wrong.details.cropFileId" alt="本题裁剪图"/><div class="original-attempt"><h3>你的答案</h3><p class="math-equation">{{wrong.answer||'未填写'}}</p><p class="preserve-lines">{{wrong.reason}}</p></div><AppDisclosure class="study-disclosure"><template #title>错因分类</template><label class="field-label" for="cause">错因</label><NativeSelect id="cause" v-model="cause" :disabled="wrong.readOnly"><option v-for="r in options.reasons" :key="r">{{r}}</option></NativeSelect><AppCheckbox class="capture-confirm" v-model="confirmed" :disabled="wrong.readOnly">确认本题错因</AppCheckbox><AppButton variant="outline" :disabled="wrong.readOnly||saving" @click="confirmCause">保存分类</AppButton></AppDisclosure><AppDisclosure v-if="wrong.repairs.length" class="repair-history"><template #title>以前的练习 　 {{wrong.repairs.length}}</template><article v-for="a in wrong.repairs" :key="a.id"><Status>{{a.details.version==='legacy_fixed'?'历史示例':a.details.phase==='retest'?'独立练习':'用过帮助'}}</Status><p>{{a.details.equation}}</p><p>作答 {{a.answer}}</p><p>{{a.reason}}</p><strong>{{a.verification?.status==='unverified'?'需要核对':a.correct?'数值正确':'需要订正'}}</strong><p v-if="a.details.version==='legacy_fixed'">{{a.details.scope}}</p></article></AppDisclosure></AppDialog>
    <AppDialog v-model:open="assistantOpen" title="学习助手" content-class="student-help-dialog"><AppAlert  v-if="job.busy.value" role="status" class="inline-notice" data-status="active">{{job.job.value?.step||'正在准备提示…'}}</AppAlert><AppAlert type="error" v-if="job.error.value||job.job.value?.status==='failed'" role="alert" class="form-error">{{job.error.value||job.job.value.error}}<AppButton :disabled="job.busy.value||wrong.readOnly" variant="outline" @click="job.job.value?.status==='failed'?job.retry():load(false)">重试</AppButton></AppAlert><div class="remediation-strategies"><AppButton v-for="[value,label] in strategies" :key="value" variant="outline" :disabled="wrong.readOnly||job.busy.value" @click="create('guidance',value)">{{label}}</AppButton></div><article v-for="j in guidance.slice(-1)" :key="j.id" class="remediation-turn"><p v-if="j.prompt" class="remediation-student">{{j.prompt}}</p><template v-if="j.result"><h3>{{j.result.title}}</h3><p>{{j.result.hint}}</p><ol><li v-for="step in j.result.steps" :key="step">{{step}}</li></ol><p class="remediation-question">{{j.result.question}}</p><AppDisclosure v-if="j.result.sources?.length"><template #title>参考来源</template><div v-for="source in j.result.sources" :key="source.versionId"><strong>{{source.title}}</strong><a v-for="ref in source.references||[]" :key="ref.unitId" :href="'#/source?unit='+ref.unitId" target="_blank" rel="noopener">{{ref.materialTitle||'原文'}} 　 {{ref.label}}</a></div></AppDisclosure></template><p v-else>{{j.error||j.step}}</p></article><AppDisclosure v-if="guidance.length>1" class="study-disclosure"><template #title>前面的指导 　 {{guidance.length-1}}</template><article v-for="j in guidance.slice(0,-1)" :key="j.id"><p>{{j.prompt}}</p><h3>{{j.result?.title}}</h3><p>{{j.result?.hint||j.error||j.step}}</p><ol><li v-for="step in j.result?.steps||[]" :key="step">{{step}}</li></ol><p>{{j.result?.question}}</p></article></AppDisclosure></AppDialog>
  </template>
</template>
