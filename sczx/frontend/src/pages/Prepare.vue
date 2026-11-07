<script setup>
import { computed, inject, ref, onBeforeUnmount, watch } from "vue";
import { useLearning } from "@/store.js";
import { navigate } from "@/lib/navigation.js";

import {
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Send,
  Eye,
  FileText,
  LibraryBig,
  Save,
  GripVertical,
  WandSparkles,
} from "lucide-vue-next";
import draggable from "vuedraggable";
import Workspace from "@/components/Workspace.vue";
import LessonPreview from "@/components/LessonPreview.vue";
import { initialBlocks } from "@/data.js";
const store = useLearning(),
  notify = inject("notify");

const modal = ref(""),
  previewTab = ref("student"),
  busyBlock = ref(""),
  publishClass = ref(store.data.publishClassId || store.data.classroom?.id || store.data.classrooms?.[0]?.id || ""),
  publishError = ref("");
watch(() => store.data.classrooms, (classrooms) => {
  if (!publishClass.value && classrooms?.length) publishClass.value = classrooms[0].id;
}, { immediate: true, deep: true });
const dialogOpen = computed({
  get: () => !!modal.value,
  set: (value) => {
    if (!value) modal.value = "";
  },
});
let timer;
function regenerate(id) {
  busyBlock.value = id;
  timer = setTimeout(() => {
    store.data.lessonDraft.blocks.find((block) => block.id === id).content =
      initialBlocks.find((block) => block.id === id).content +
      " 请先预测，再解释理由。";
    busyBlock.value = "";
    store.touch();
    notify("演示建议已生成");
  }, 500);
}
onBeforeUnmount(() => clearTimeout(timer));
function reorderKeyboard(event, index) {
  if (!["ArrowUp", "ArrowDown"].includes(event.key)) return;
  event.preventDefault();
  const target = index + (event.key === "ArrowUp" ? -1 : 1);
  if (target < 0 || target >= store.blocks.length) return;
  const blocks = [...store.blocks];
  [blocks[index], blocks[target]] = [blocks[target], blocks[index]];
  store.data.lessonDraft.blocks = blocks;
  store.touch();
}
async function saveDraft() {
  notify((await store.save()) ? "教案已保存" : store.saveError);
}
async function publish() {
  publishError.value = "";
  if (!publishClass.value) {
    publishError.value = "请先创建班级并加入学生，再发布任务。";
    return;
  }
  store.data.publishClassId = publishClass.value;
  try {
    const task = await store.publish();
    if (task) {
      modal.value = "";
      navigate("class");
      notify("任务已发布");
    }
  } catch (error) {
    publishError.value = error.message;
  }
}
</script>
<template>
  <div class="back-line">
    <Button variant="ghost" @click="navigate('teacher')"
      ><ArrowLeft />返回教学概览</Button
    ><span>我的教案 / 等式性质</span>
  </div>
  <PageHeading title="等式性质 · 备课"
    ><Button variant="outline" @click="saveDraft"><Save />保存教案</Button
    ><Button variant="outline" @click="modal = 'preview'"
      ><Eye />学生预览</Button
    ><Button @click="modal = 'publish'"
      ><Send />{{ store.data.tasks.length ? "再次发布" : "发布任务" }}</Button
    ></PageHeading
  ><Workspace
    ><template #primary
      ><div class="lesson-editor">
        <div class="editor-intro">
          <span><FileText :size="16" />教师教学安排</span
          ><Status>{{
            store.saving
              ? "保存中"
              : store.saveError
                ? "保存失败"
                : store.savedAt
                  ? "已保存"
                  : "已连接"
          }}</Status>
        </div>
        <label class="field-label" for="lesson-goal">本课目标</label
        ><Input id="lesson-goal" v-model="store.data.lessonDraft.goal" /><label
          class="field-label"
          for="student-base"
          >学生基础</label
        ><Input
          id="student-base"
          v-model="store.data.lessonDraft.studentBase"
        />
        <div class="editor-section-heading">
          <h2>教学活动</h2>
          <InfoTip label="调整活动顺序"
            >拖动手柄或聚焦手柄后按上下方向键调整顺序。</InfoTip
          >
        </div>
        <draggable
          v-model="store.data.lessonDraft.blocks"
          item-key="id"
          handle=".drag-handle"
          :force-fallback="true"
          :fallback-on-body="true"
          :fallback-tolerance="3"
          class="sortable-list"
          :animation="0"
          ghost-class="dragging"
          @end="notify('教学活动与学生预览已同步排序')"
          ><template #item="{ element: block, index }"
            ><div class="editor-block">
              <div class="editor-block-heading">
                <button
                  class="drag-handle"
                  :aria-label="`拖动排序：${block.title}`"
                  @keydown="reorderKeyboard($event, index)"
                >
                  <GripVertical :size="16" />
                </button>
                <h3>{{ block.title }}</h3>
                <Button
                  size="icon-xs"
                  variant="ghost"
                  :aria-label="`重新生成${block.title}`"
                  :disabled="busyBlock === block.id"
                  @click="regenerate(block.id)"
                  ><WandSparkles
                /></Button>
              </div>
              <Textarea
                v-model="block.content"
                :aria-label="block.title"
                :disabled="busyBlock === block.id"
              /></div></template></draggable
        ><button class="reference-link" @click="navigate('case-detail')">
          <LibraryBig :size="16" /><span>参考案例 · 天平与等式性质</span
          ><ArrowUpRight :size="15" />
        </button></div></template
    ><template #secondary
      ><div class="preview-pane-tabs">
        <AppTabs
          v-model="previewTab"
          :items="[
            { value: 'student', label: '学生内容' },
            { value: 'source', label: '参考经验' },
          ]"
        />
      </div>
      <LessonPreview v-if="previewTab === 'student'" />
      <div v-else class="preview-source">
        <BookOpen :size="28" />
        <h2>天平与等式性质</h2>
        <p>
          先预测，再操作，最后解释。根据学生回应调整讲法，将“同时”和“相同”落实到每一步。
        </p>
        <RouteButton route="case-detail" secondary>阅读完整案例</RouteButton>
      </div></template
    ></Workspace
  ><AppDialog
    v-model:open="dialogOpen"
    :title="modal === 'preview' ? '学生预览' : '发布学习任务'"
    :content-class="
      modal === 'preview' ? 'lesson-preview-dialog' : 'publish-dialog'
    "
    ><template v-if="modal === 'preview'"
      ><LessonPreview /><Button @click="modal = 'publish'"
        >继续发布<ArrowRight /></Button></template
    ><template v-else
      ><p v-if="publishError" class="form-error" role="alert">
        {{ publishError }}
      </p>
      <div class="publish-course">
        <FileText :size="22" />
        <div>
          <strong>等式性质</strong
          ><small>{{ store.data.lessonDraft.blocks.length }} 个活动</small>
        </div>
      </div>
      <label class="field-label" for="publish-class">发布班级</label
      ><AppSelect
        id="publish-class"
        v-model="publishClass"
        label="选择发布班级"
        :options="store.data.classrooms.map((item) => ({ value: item.id, label: `${item.name} · ${item.grade}` }))" /><p v-if="!store.data.classrooms.length" class="form-error">先在班级教学中创建班级并添加学生。</p><label
        class="field-label"
        for="due-date"
        >建议完成日期</label
      ><Input
        id="due-date"
        v-model="store.data.lessonDraft.dueDate"
        type="date" />
      <p class="small-caption">发布后，所选班级的学生可从任务列表进入本课。</p>
      <Button @click="publish" :disabled="store.publishing || !store.data.classrooms.length"
        >{{ store.publishing ? "发布中…" : "确认发布"
        }}<ArrowRight /></Button></template
  ></AppDialog>
</template>
