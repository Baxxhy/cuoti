<script setup>
import UnitJourney from "@/components/UnitJourney.vue";
import MemoryBridge from "@/components/MemoryBridge.vue";
import MemoryReturn from "@/components/MemoryReturn.vue";
import SupplementPanel from "@/components/SupplementPanel.vue";
import { computed, ref, inject, watch, nextTick } from "vue";
import { CheckCircle2, ChevronRight } from "lucide-vue-next";
import { useLearning } from "@/store.js";
import Workspace from "@/components/Workspace.vue";
import LessonContent from "@/components/LessonContent.vue";
import QuestionAttempt from "@/components/QuestionAttempt.vue";
import ModelAssistant from "@/components/ModelAssistant.vue";
import TaskEmpty from "@/components/TaskEmpty.vue";
const store = useLearning(),
  notify = inject("notify");
const saving = ref(false),
  sideTab = ref("outline"),
  selectedBlock = ref(null),
  selectedQuestion = ref(null);
function selectBlock(id, question = null) {
  selectedBlock.value = id;
  selectedQuestion.value = question;
  if (store.record && !store.task?.readOnly) {
    store.record.drafts.lessonPosition = { blockId: id, question };
    store.touch();
  }
}
function guide(id, question) {
  selectBlock(id, question);
  sideTab.value = "help";
  nextTick(() => {
    const input = document.querySelector(
      ".tutoring-assistant #learning-question",
    );
    input?.focus({ preventScroll: true });
    input?.scrollIntoView({
      block: "nearest",
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "auto"
        : "smooth",
    });
  });
}
watch(
  () => store.record?.id,
  async () => {
    const position = store.record?.drafts.lessonPosition;
    selectedBlock.value = (store.task?.snapshot.blocks || []).some(
      (b) => b.id === position?.blockId,
    )
      ? position.blockId
      : store.task?.snapshot.blocks?.[0]?.id || null;
    selectedQuestion.value = position?.question ?? null;
    await nextTick();
    if (position?.blockId)
      document
        .querySelector(`[data-block="${CSS.escape(position.blockId)}"]`)
        ?.scrollIntoView({ block: "start" });
  },
  { immediate: true, flush: "sync" },
);
const lesson = computed(() => ({
  ...store.task?.snapshot,
  title: store.task?.title,
  questions: store.task?.questions || [],
}));
const progress = computed(() => {
  const values = { ...store.record?.drafts.blocks };
  for (const block of store.task?.snapshot.blocks || []) {
    if (["practice", "check"].includes(block.type)) {
      const ids = new Set(
        (store.record?.attempts || []).map(
          (a) => store.task.questions[a.question]?.id,
        ),
      );
      values[block.id] = {
        completed:
          !!block.questionIds?.length &&
          block.questionIds.every((id) => ids.has(id)),
      };
    }
  }
  return values;
});
const completed = computed(
  () => Object.values(progress.value).filter((v) => v.completed).length,
);
function update(id, value) {
  if (!store.record || store.task?.readOnly) return;
  store.record.drafts.blocks ||= {};
  store.record.drafts.blocks[id] = value;
  store.record.observation = Object.values(store.record.drafts.blocks)
    .map((b) => b.explanation)
    .filter(Boolean)
    .join("\n");
  store.touch();
}
function locate(id) {
  selectBlock(id);
  document.querySelector(`[data-block="${CSS.escape(id)}"]`)?.scrollIntoView({
    block: "start",
    behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
      ? "auto"
      : "smooth",
  });
}
async function save() {
  saving.value = true;
  notify((await store.save()) ? "学习进度已保存" : store.saveError);
  saving.value = false;
}
</script>
<template>
<MemoryReturn/>
  <template v-if="store.task"
    ><PageHeading :title="store.task.title"
      ><Button
        variant="outline"
        :disabled="saving || store.task.readOnly"
        @click="save"
        >{{ saving ? "保存中…" : "保存进度" }}</Button
      ><RouteButton :route="'check?task='+store.task.id">独立检查</RouteButton
      ></PageHeading
    >
    <div v-if="lesson.blocks?.length" class="curriculum-study-meta">
      <span>{{ store.task.snapshot.lessonSnapshot?.grade || "课程学习" }}</span
      ><span>{{ completed }} / {{ lesson.blocks?.length || 0 }} 已读</span><InfoTip v-if="store.task.snapshot.lessonSnapshot" label="课时版本">v{{ store.task.snapshot.lessonSnapshot.version }}</InfoTip>
    </div>
    <Workspace v-if="lesson.blocks?.length"
      ><template #primary
        ><p v-if="store.task.readOnly" class="inline-notice">
          已移出班级，此任务仅可回看。
        </p>
        <fieldset class="history-fields" :disabled="store.task.readOnly">
          <LessonContent
            :lesson="lesson"
            :progress="progress"
            @progress="update"
            @focus="selectBlock"
            ><template #question="{ question, index, block }"
              ><QuestionAttempt
                v-if="block.type === 'practice'"
                :key="question.id"
                :question="question"
                :index="index"
                @guide="guide(block.id, $event)"
              /><RouteButton v-else :route="'check?task='+store.task.id" secondary
                >进入独立检查</RouteButton
              ></template
            ></LessonContent
          >
        </fieldset>
        <details class="study-disclosure"><summary>教师补充内容</summary><SupplementPanel :task-id="store.task.id" /></details><div class="study-complete action-row"><RouteButton :route="'check?task='+store.task.id">开始独立检查</RouteButton><RouteButton :route="'result?task='+store.task.id" secondary>查看学习结果</RouteButton></div></template
      ><template #secondary
        ><AppTabs v-model="sideTab" :items="[{value:'outline',label:'本课目录'},{value:'help',label:'学习助手'}]"/><nav v-if="sideTab==='outline'" class="curriculum-outline" aria-label="本课内容">
          <div class="library-pane-heading">
            <h2>本课内容</h2>
            <InfoTip label="内容来源">{{
              store.task.snapshot.lessonSnapshot?.source ||
              "历史任务内容，版本来源未记录"
            }}</InfoTip>
          </div>
          <button
            v-for="(block, i) in lesson.blocks"
            :key="block.id"
            @click="locate(block.id)"
            :aria-current="selectedBlock === block.id ? 'step' : null"
          >
            <span>{{ String(i + 1).padStart(2, "0") }}</span
            ><strong>{{ block.title }}</strong
            ><CheckCircle2
              v-if="progress[block.id]?.completed"
              :size="16"
            /><ChevronRight v-else :size="16" />
          </button>
        </nav>
        <ModelAssistant
          v-else
          :key="store.task.id"
          :question="selectedQuestion"
          :block-id="selectedBlock" /></template></Workspace>
    <section v-else class="student-practice-task">
      <p v-if="lesson.goal" class="student-practice-goal">{{lesson.goal}}</p>
      <template v-if="lesson.questions.length">
        <div class="section-heading"><h2>本次练习</h2><span>{{lesson.questions.length}} 题</span></div>
        <ol class="student-practice-preview"><li v-for="(question,i) in lesson.questions" :key="question.id||i"><span>{{String(i+1).padStart(2,'0')}}</span><div><strong>{{question.prompt}}</strong><p v-if="question.equation" class="math-equation">{{question.equation}}</p></div></li></ol>
        <div class="action-row"><RouteButton :route="'check?task='+store.task.id">开始独立练习</RouteButton><RouteButton :route="'result?task='+store.task.id" secondary>查看学习结果</RouteButton></div>
      </template>
      <template v-else><p class="muted">本任务没有练习题。</p><RouteButton :route="'result?task='+store.task.id">查看学习结果</RouteButton></template>
      <details class="study-disclosure"><summary>教师补充内容</summary><SupplementPanel :task-id="store.task.id"/></details>
    </section></template
  ><TaskEmpty v-else />
<details v-if="store.task" class="study-disclosure"><summary>复习与单元进度</summary><MemoryBridge :task="store.task" compact/><UnitJourney v-if="store.task?.unitId||store.task?.snapshot.lessonSnapshot?.unitId" :unit-id="store.task.unitId||store.task.snapshot.lessonSnapshot.unitId" :task="store.task" compact/></details></template>
