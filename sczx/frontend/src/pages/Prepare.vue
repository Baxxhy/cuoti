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
import CaseArticle from "@/components/CaseArticle.vue";
import { modelApi } from "@/services/models.js";
import { curriculumApi } from "@/services/curriculum.js";
import {useRoute} from "vue-router";
const store = useLearning(),
  notify = inject("notify");

const route=useRoute();const templateBusy=ref(false);
watch(()=>route.query.lesson,async id=>{if(id&&id!==store.data.lesson?.id){try{await store.selectLesson(String(id))}catch(e){notify(e.message)}}},{immediate:true});
async function applyPublished(){if(!confirm('使用当前发布课时替换本教案的目标、活动、题目与引用？学生基础、截止日期和已有任务保留。'))return;templateBusy.value=true;try{const data=await curriculumApi.lesson(store.data.lesson.id);Object.assign(store.data.lessonDraft,{lessonId:store.data.lesson.id,lessonSnapshot:data,goal:data.goal,blocks:structuredClone(data.blocks),questions:structuredClone(data.questions),caseId:data.caseId,caseSnapshot:data.caseSnapshot});store.touch();notify(await store.save()?'已使用发布课时内容':store.saveError)}catch(e){notify(e.message)}finally{templateBusy.value=false}}
const caseSnapshot = computed(() => store.data.lessonDraft.caseSnapshot);
const fallbackCase=ref(null),referenceError=ref('');let referenceGeneration=0;
const caseReference=computed(()=>caseSnapshot.value?.versionId?caseSnapshot.value:fallbackCase.value);
watch(()=>[store.data.lessonDraft.caseId,caseSnapshot.value?.versionId],async([id,versionId])=>{const generation=++referenceGeneration;fallbackCase.value=null;referenceError.value='';if(!id||versionId)return;try{const item=await modelApi.caseDetail(id);if(generation===referenceGeneration)fallbackCase.value=item}catch(e){if(generation===referenceGeneration)referenceError.value=e.message}},{immediate:true});
const caseRoute = computed(() => 'case-detail?caseId='+encodeURIComponent(store.data.lessonDraft.caseId||'')+(caseSnapshot.value?.versionId?'&versionId='+encodeURIComponent(caseSnapshot.value.versionId):''));
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
  const original=store.data.lessonDraft.lessonSnapshot?.blocks?.find(b=>b.id===id);
  if(!original)return notify('此活动没有对应发布原稿，请直接编辑。');
  if(confirm('恢复此活动的发布原稿？其他活动保留。')){store.data.lessonDraft.blocks.find(b=>b.id===id).content=original.content;store.touch()}
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
    ><span>我的教案 / {{ store.data.lesson?.title }}</span>
  </div>
  <PageHeading :title="(store.data.lesson?.title||'课时')+' · 备课'"
    ><RouteButton :route="'agent?lesson='+store.data.lesson?.id" secondary>任务备课</RouteButton><Button variant="outline" :disabled="templateBusy" @click="applyPublished">使用发布课时</Button><RouteButton route="courses" secondary>选择课时</RouteButton><Button variant="outline" @click="saveDraft"><Save />保存教案</Button
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
                  :aria-label="`恢复原稿：${block.title}`"
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
        ><details class="curriculum-teacher-questions"><summary>编辑题目 · {{ store.data.lessonDraft.questions?.length||0 }}</summary><div v-for="q in store.data.lessonDraft.questions" :key="q.id||q.equation"><label v-for="(label,key) in {prompt:'题干',equation:'方程',answer:'参考答案',hint:'提示'}" :key="key">{{ label }}<Input v-model="q[key]"/></label></div></details><button class="reference-link" @click="navigate(caseRoute)" :disabled="!store.data.lessonDraft.caseId">
          <LibraryBig :size="16" /><span>参考案例 · {{ caseReference?.title || '尚未选择' }}</span
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
        <h2>{{ caseReference?.title || '尚未选择参考案例' }}</h2>
        <InfoTip v-if="caseReference&&!caseSnapshot?.versionId" label="参考版本说明">此教案尚未记录案例版本，当前展示最新发布内容；使用案例备课后会保存所选版本。</InfoTip><p v-if="referenceError" class="form-error">{{ referenceError }}</p><CaseArticle v-if="caseReference" :value="caseReference" />
        <RouteButton v-if="store.data.lessonDraft.caseId" :route="caseRoute" secondary>阅读完整案例</RouteButton>
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
          <strong>{{ store.data.lesson?.title }}</strong
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
