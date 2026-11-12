<script setup>
import MatchEvidence from "./MatchEvidence.vue";
import { computed, ref, watch } from "vue";
import { LoaderCircle, RotateCcw, Check, CircleAlert } from "@/components/app/icons.js";
import SpeechReader from "./SpeechReader.vue";
import { capabilityNames } from "@/services/models.js";
const props = defineProps({
  job: Object,
  busy: Boolean,
  showSource: Boolean,
  canRetry: { type: Boolean, default: true },
});
defineEmits(["retry"]);
const expanded = ref(false), stepIndex=ref(0);
const uniqueReferences = (refs) => [
  ...new Map((refs || []).map((item) => [item.unitId, item])).values(),
];
watch(
  () => props.job?.id,
  () => {
    expanded.value = false;
    stepIndex.value=0;
  },
);
const result = computed(() => props.job?.result);
const verification = computed(
  () =>
    ({
      verified: "列出的等式已核对",
      inconsistent: "发现数学不一致",
      unverified: result.value?.verification?.claims?.length?"数学需核对":"待教师核对",
    })[result.value?.verification?.status],
);
</script>
<template>
  <section v-if="job" class="model-result" :aria-busy="busy">
    <AppAlert v-if="busy || job.status==='failed'" :type="job.status==='failed'?'error':'info'" class="model-status" role="status" aria-live="polite">
      <strong>{{ capabilityNames[job.capability] }}</strong
      ><span>{{ job.step }}</span>
    </AppAlert>
    <AppAlert type="error" v-if="job.error" class="model-error" role="alert">{{ job.error }}</AppAlert>
    <AppButton
      v-if="canRetry && job.status === 'failed'"
      variant="outline"
      :disabled="busy"
      @click="$emit('retry')"
      ><RotateCcw :size="16" />重试</AppButton
    >
    <AppImage
      v-if="
        showSource && job.fileId && ['text', 'ocr'].includes(job.capability)
      "
      :src="`/api/files/${job.fileId}`"
      class="ai-original"
      alt="原始题图"
    />
    <audio
      v-if="showSource && job.fileId && job.capability === 'asr'"
      :src="`/api/files/${job.fileId}`"
      class="model-audio"
      controls
      aria-label="转写原始音频"
    />
    <template v-if="result && job.status === 'succeeded'">
      <AppDisclosure v-if="job.recognizedText" class="model-run-history">
        <template #title>学生确认的题目</template>
        <p class="model-prose">{{ job.recognizedText }}</p>
      </AppDisclosure>
      <template v-if="job.mode==='analysis'"><h3>{{result.goal}}</h3><p class="model-prose">建议检查：{{result.cause}}</p><blockquote v-if="result.evidence">{{result.evidence}}</blockquote><p class="model-prose">{{result.uncertainty}}</p><ElTimeline><ElTimelineItem v-for="(step,index) in result.steps" :key="index" type="primary">{{step}}</ElTimelineItem></ElTimeline><AppAlert type="info" class="model-followup">{{result.checkQuestion}}</AppAlert></template>
      <template v-else-if="job.mode==='variant'"><h3>{{job.phase==='retest'?'独立新题':'补救练习'}}</h3><p class="model-prose">{{result.variant?.prompt}}</p><p class="math-equation">{{result.variant?.equation}}</p><Status>{{result.variantVerification?.status==='verified'?'本题方程与参考答案已核对':'需要核对'}}</Status></template>
      <template v-else-if="job.capability === 'text'">
        <SpeechReader
          :text="
            [result.title, result.hint, ...(expanded ? [result.steps?.[stepIndex]] : [])]
              .filter(Boolean)
              .join('。')
          "
        />
        <Status v-if="showSource&&job.strategy">{{
          {
            hint: "提示",
            example: "举例",
            rephrase: "换讲法",
            foundation: "补基础",
            try: "自主尝试",
          }[job.strategy]
        }}</Status>
        <h3>{{ result.title }}</h3>
        <AppAlert type="info" class="model-prose">{{ result.hint }}</AppAlert>
        <AppButton
          v-if="result.steps?.length"
          variant="ghost"
          @click="expanded = !expanded"
          :aria-expanded="expanded"
          >{{ expanded ? "收起步骤" : "一步步看" }}</AppButton
        >
        <Surface v-if="expanded&&result.steps?.length" class="student-model-step"><span>{{stepIndex+1}} / {{result.steps.length}}</span><p>{{result.steps[stepIndex]}}</p><div class="action-row"><AppButton variant="ghost" size="sm" :disabled="stepIndex===0" @click="stepIndex--">上一步</AppButton><AppButton variant="outline" size="sm" :disabled="stepIndex===result.steps.length-1" @click="stepIndex++">下一步</AppButton></div></Surface>
        <AppAlert v-if="result.question" type="info" class="model-followup">
          {{ result.question }}
        </AppAlert>
        <div v-if="job.strategy !== 'try'" class="model-verification">
          <Status
            :tone="
              result.verification?.status === 'verified' ? 'green' : 'amber'
            "
            >{{ verification }}</Status
          ><InfoTip label="核对范围">{{
            result.verification?.scope
          }}</InfoTip>
        </div>
      </template>
      <p v-else-if="result.text" class="model-prose">{{ result.text }}</p>
      <p v-if="result.equation" class="model-prose">{{ result.equation }}</p>
      <p v-if="result.studentAnswer" class="model-prose">
        原作答：{{ result.studentAnswer }}
      </p>
      <AppAlert type="warning" v-if="result.uncertainties?.length" class="model-error">
        待核对：{{ result.uncertainties.join("；") }}
      </AppAlert>
      <div v-if="job.capability === 'embedding'" class="model-metrics">
        <div>
          <strong>{{ result.count }}</strong
          ><span>段文本</span>
        </div>
        <div>
          <strong>{{ result.dimensions }}</strong
          ><span>向量维度</span>
        </div>
      </div>
      <div v-if="job.capability === 'retrieval'" class="retrieval-results">
        <p v-if="!result.items?.length" class="ai-empty">
          没有匹配的案例，换个知识点或学生困难试试。
        </p>
        <AppAlert v-if="result.warning" type="warning" role="status" class="model-model-name">
          {{ result.warning }}
        </AppAlert>
        <AppDisclosure
          v-for="item in result.items"
          :key="item.id"
          class="retrieval-item"
        >
          <template #title>{{ item.title }}</template>
          <p class="model-prose">{{ item.content }}</p>
          <MatchEvidence :item="item" /><span class="model-model-name">{{
            item.source || "团队编写案例示例"
          }}</span>
        </AppDisclosure>
        <InfoTip v-if="result.items?.length" label="检索方式"
          >BM25 中文检索{{
            result.rerankApplied ? "，已完成 Codex 语义重排" : ""
          }}；相关分值不代表内容正确性。</InfoTip
        >
      </div>
      <AppDisclosure v-if="result.sources?.length" class="model-run-history">
        <template #title>参考教学案例 　 {{ result.sources.length }}</template>
        <section
          v-for="source in result.sources"
          :key="`${source.id}:${source.versionId || ''}`"
        >
          <p>
            {{
              source.role === "lesson"
                ? source.roles?.includes("retrieval")
                  ? "课时关联 / 情境检索 　 "
                  : "课时关联 　 "
                : "情境检索 　 "
            }}{{ source.title
            }}{{ source.version ? " 　 v" + source.version : "" }}
          </p>
          <MatchEvidence :item="source" /><a
            v-for="(ref, index) in uniqueReferences(source.references)"
            :key="index"
            :href="`/#/source?unit=${ref.unitId}`"
            target="_blank"
            rel="noopener"
            >{{ ref.materialTitle }} 　 {{ ref.label }}</a
          >
        </section>
      </AppDisclosure>
      <ol v-if="result.ranking" class="model-ranking">
        <li v-for="item in result.ranking" :key="item.id">
          <strong>{{ item.id }}</strong
          ><span>{{ item.score }}</span>
        </li>
      </ol>
      <InfoTip v-if="result.scoreMeaning" label="重排方法与分值"
        >{{ result.method === "llm" ? "LLM 语义重排。" : ""
        }}{{ result.scoreMeaning }}</InfoTip
      >
      <audio
        v-if="result.url"
        class="model-audio"
        controls
        :src="result.url"
        aria-label="生成的讲解音频"
        preload="metadata"
      />
    </template>
    <div v-if="showSource&&result?.workflow" class="tutoring-audit">
      <InfoTip label="本轮指导记录"
        >最近{{ result.workflow.historyTurns }}轮 　
        {{ result.workflow.modelCalls }}次模型调用 　
        {{ (result.workflow.elapsedMs / 1000).toFixed(1) }}秒。{{
          result.workflow.nodes.join(" → ")
        }}</InfoTip
      >
    </div>
    <AppDisclosure v-if="showSource&&job.runs?.length" class="model-run-history model-technical-details">
      <template #title>执行记录 　 {{ job.runs.length }}</template>
      <div v-for="run in job.runs" :key="run.id">
        <span
          >第 {{ run.number }} 次 　
          {{
            { running: "执行中", succeeded: "成功", failed: "失败" }[run.status]
          }}</span
        ><span>{{ run.model }}</span>
        <AppAlert v-if="run.error" type="error">{{ run.error }}</AppAlert>
      </div>
    </AppDisclosure>
  </section>
</template>
