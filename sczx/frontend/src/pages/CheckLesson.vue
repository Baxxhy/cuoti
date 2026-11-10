<script setup>
import {useRoute} from "vue-router";
import MemoryReturn from "@/components/MemoryReturn.vue";
import SupplementPanel from "@/components/SupplementPanel.vue";
import { ref, computed, watch, inject, nextTick } from "vue";
import { useLearning } from "@/store.js";
import QuestionAttempt from "@/components/QuestionAttempt.vue";
import ModelAssistant from "@/components/ModelAssistant.vue";
import TaskEmpty from "@/components/TaskEmpty.vue";
import { ArrowRight } from "lucide-vue-next";
const route=useRoute();
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
const restoring = ref(false);
watch(
  () => [store.record?.id,route.query.question],
  async () => {
    restoring.value = true;
    const requested=route.query.question===undefined?null:Number(route.query.question);
    const saved = indices.value.some(q=>q.index===requested)?requested:store.record?.drafts.check?.question;
    index.value = indices.value.some((q) => q.index === saved)
      ? saved
      : (indices.value[0]?.index ?? 0);
    await nextTick();
    restoring.value = false;
  },
  { immediate: true, flush: "sync" },
);
const blockId = computed(
  () =>
    (store.task?.snapshot.blocks || []).find((b) =>
      b.questionIds?.includes(current.value?.id),
    )?.id || null,
);
watch(index, (value) => {
  if (store.record && !store.task?.readOnly && !restoring.value) {
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
<MemoryReturn/>
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
          :key="store.task.id + ':' + index"
          :question="index"
          :block-id="blockId"
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
