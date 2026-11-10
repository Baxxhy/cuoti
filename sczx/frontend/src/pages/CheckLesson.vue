<script setup>
import SupplementPanel from "@/components/SupplementPanel.vue";
import { ref, computed, watch, inject } from "vue";
import { useLearning } from "@/store.js";
import QuestionAttempt from "@/components/QuestionAttempt.vue";
import ModelAssistant from "@/components/ModelAssistant.vue";
import TaskEmpty from "@/components/TaskEmpty.vue";
import { ArrowRight } from "lucide-vue-next";
const store = useLearning(),
  notify = inject("notify");
const indices = computed(() =>
  (store.task?.questions || [])
    .map((q, i) => ({ ...q, index: i }))
    .filter((q) => !q.kind || q.kind !== "practice"),
);
const index = ref(
  store.record?.drafts.check?.question ?? indices.value[0]?.index ?? 0,
);
const hasNext = computed(
  () =>
    indices.value.findIndex((q) => q.index === index.value) <
    indices.value.length - 1,
);
const current = computed(() =>
  indices.value.find((q) => q.index === index.value),
);
watch(index, (value) => {
  if (store.record && !store.task?.readOnly) {
    store.record.drafts.check = { question: value };
    store.touch();
  }
});
if (!current.value && indices.value.length)
  index.value = indices.value[0].index;
function next() {
  const pos = indices.value.findIndex((q) => q.index === index.value);
  if (pos + 1 >= indices.value.length)
    return notify("本任务没有更多新题，已有作答已保留。");
  index.value = indices.value[pos + 1].index;
}
function markHelp() {
  if (!store.record) return;
  const id = current.value.id || String(index.value);
  store.record.drafts.questions ||= {};
  store.record.drafts.questions[id] = {
    ...store.record.drafts.questions[id],
    helped: true,
  };
  store.touch();
}
</script>
<template>
  <template v-if="store.task"
    ><PageHeading :title="store.task.title + ' · 独立检查'"
      ><RouteButton route="learn" secondary>返回本课</RouteButton></PageHeading
    >
    <div v-if="current" class="check-grid">
      <Surface class="question-card"
        ><div class="question-meta">
          <span
            >{{ indices.findIndex((q) => q.index === index) + 1 }} /
            {{ indices.length }}</span
          ><Status>{{
            current.kind === "replacement" ? "新题检查" : "独立检查"
          }}</Status>
        </div>
        <h2>{{ current.prompt }}</h2>
        <p class="question-equation">{{ current.equation }}</p>
        <fieldset class="history-fields" :disabled="store.task.readOnly">
          <QuestionAttempt
            :key="store.task.id + ':' + index"
            :question="current"
            :index="index"
          /></fieldset
      ></Surface>
      <aside class="check-aside">
        <ModelAssistant
          v-if="!store.task.readOnly"
          :key="store.task.id + ':' + index"
          :question="index"
          compact
          @help="markHelp"
        /><InfoTip label="独立检查规则"
          >本题获得帮助后保留指导记录；换题会重新记录独立尝试。提交只表示完成流程，是否独立正确单独记录。</InfoTip
        ><Button variant="outline" :disabled="!hasNext" @click="next"
          >{{ hasNext ? "换一道新题" : "暂无更多新题" }}<ArrowRight /></Button
        ><RouteButton route="result" secondary>查看本课结果</RouteButton>
      </aside>
    </div>
    <div v-else class="empty-state">
      <h3>本任务没有可用检查题</h3>
      <RouteButton route="result" secondary>返回学习结果</RouteButton>
    </div></template
  ><TaskEmpty v-else />
</template>
