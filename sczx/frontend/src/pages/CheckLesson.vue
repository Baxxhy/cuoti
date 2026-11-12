<script setup>
import MathExpression from "@/components/MathExpression.vue";
import EquationTool from "@/components/EquationTool.vue";
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
const helpOpen=ref(false), toolOpen=ref(false);
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
  <template v-if="store.task">
    <PageHeading title="独立练习"><RouteButton :route="'learn?task='+store.task.id" secondary>返回本课</RouteButton></PageHeading>
    <section v-if="current" class="student-check-focus">
      <div class="student-check-topline"><span>{{store.task.title}}</span><div><Button variant="ghost" @click="helpOpen=true">需要帮助</Button><InfoTip label="获得帮助后的记录">本题获得帮助后会保留帮助记录，换题重新记录独立尝试。</InfoTip></div></div>
      <nav class="student-question-dots" aria-label="练习题目"><button v-for="(item,n) in indices" :key="item.index" :class="{active:index===item.index,answered:store.record?.attempts.some(a=>a.question===item.index)}" :aria-label="'第'+(n+1)+'题'" :aria-current="index===item.index?'step':undefined" @click="index=item.index">{{n+1}}</button></nav>
      <article class="question-card student-check-card">
        <div class="student-check-prompt"><h2>{{current.prompt}}</h2><div v-if="current.equation" class="question-equation"><MathExpression :text="current.equation"/></div></div>
        <fieldset class="history-fields" :disabled="store.task.readOnly"><QuestionAttempt :key="store.task.id+':'+index" :question="current" :index="index" @guide="helpOpen=true"/></fieldset>
        <div class="student-question-next"><Button variant="ghost" @click="toolOpen=true">试着变形</Button><Button v-if="hasNext" variant="outline" @click="next">下一题<ArrowRight :size="16"/></Button><RouteButton v-else :route="'result?task='+store.task.id">完成练习</RouteButton></div>
      </article>
    </section>
    <div v-else class="empty-state"><h3>本任务没有练习题</h3><RouteButton :route="'result?task='+store.task.id">查看学习结果</RouteButton></div>
    <AppDialog v-model:open="helpOpen" title="学习助手" content-class="student-help-dialog"><ModelAssistant v-if="current" :key="store.task.id+':'+index" :question="index" :block-id="blockId" compact :show-heading="false" @help="markHelp"/></AppDialog>
    <AppDialog v-model:open="toolOpen" title="方程变形" content-class="student-tool-dialog"><EquationTool v-if="store.record&&current" :record-id="store.record.id" :question="index"/></AppDialog>
  </template><TaskEmpty v-else/>
</template>
