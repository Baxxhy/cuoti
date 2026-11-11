<script setup>
import { computed, inject, ref, watch } from "vue";
import { useLearning } from "@/store.js";
import { navigate } from "@/lib/navigation.js";

import {
  ArrowRight,
  ArrowUpRight,
  Send,
  Eye,
  FileText,
  LibraryBig,
  Save,
  GripVertical,
  WandSparkles,
} from "lucide-vue-next";
import draggable from "vuedraggable";
import PreparationTools from "@/components/PreparationTools.vue";
import LessonPreview from "@/components/LessonPreview.vue";
import CaseArticle from "@/components/CaseArticle.vue";
import { modelApi } from "@/services/models.js";
import { curriculumApi } from "@/services/curriculum.js";
import {useRoute} from "vue-router";
const store = useLearning(),
  notify = inject("notify");

const tools=ref(null);
function ensureStudentCopy(block) {
  const source=store.data.lessonDraft.lessonSnapshot?.blocks?.find(item=>item.id===block.id)||block;
  if(block.studentTitle===undefined) block.studentTitle=source.studentTitle??source.title;
  if(block.studentContent===undefined) block.studentContent=source.studentContent??source.content;
}

const workTab=ref("edit"), moreOpen=ref(false);
const details=computed(()=>store.data.lessonDraft.planningDetails|| (store.data.lessonDraft.planningDetails={}));
const route=useRoute();
watch(()=>route.query.class,id=>{if(id&&store.data.classrooms.some(c=>c.id===id))store.data.publishClassId=String(id)},{immediate:true});const templateBusy=ref(false),lessonSwitchBusy=ref(false);
watch(()=>route.query.lesson,async id=>{
 if(id&&id!==store.data.lesson?.id){
  lessonSwitchBusy.value=true;
  try{await store.selectLesson(String(id))}catch(e){notify(e.message)}finally{lessonSwitchBusy.value=false}
 }
},{immediate:true});
async function applyPublished(){if(!confirm('使用当前发布课时替换本教案的目标、活动、题目与引用？学生基础、截止日期和已有任务保留。'))return;templateBusy.value=true;const draft=store.data.lessonDraft,id=store.data.lesson.id;try{const data=await curriculumApi.lesson(id);if(store.data.lessonDraft!==draft||store.data.lesson.id!==id)return;Object.assign(draft,{lessonId:id,lessonSnapshot:data,goal:data.goal,blocks:structuredClone(data.blocks),questions:structuredClone(data.questions),caseId:data.caseId,caseSnapshot:data.caseSnapshot});store.touch();notify(await store.save()?'已使用发布课时内容':store.saveError)}catch(e){notify(e.message)}finally{templateBusy.value=false}}
const caseSnapshot = computed(() => store.data.lessonDraft.caseSnapshot);
const fallbackCase=ref(null),referenceError=ref('');let referenceGeneration=0;
const caseReference=computed(()=>caseSnapshot.value?.versionId?caseSnapshot.value:fallbackCase.value);
watch(()=>[store.data.lessonDraft.caseId,caseSnapshot.value?.versionId],async([id,versionId])=>{const generation=++referenceGeneration;fallbackCase.value=null;referenceError.value='';if(!id||versionId)return;try{const item=await modelApi.caseDetail(id);if(generation===referenceGeneration)fallbackCase.value=item}catch(e){if(generation===referenceGeneration)referenceError.value=e.message}},{immediate:true});
const caseRoute = computed(() => 'case-detail?caseId='+encodeURIComponent(store.data.lessonDraft.caseId||'')+(caseSnapshot.value?.versionId?'&versionId='+encodeURIComponent(caseSnapshot.value.versionId):''));
const modal = ref(""),
  busyBlock = ref(""),
  publishClass = ref(store.data.publishClassId || store.data.classroom?.id || store.data.classrooms?.[0]?.id || ""),
  publishError = ref("");
watch(()=>route.query.class,id=>{if(id&&store.data.classrooms.some(c=>c.id===id))publishClass.value=String(id)},{immediate:true});
watch(() => store.data.classrooms, (classrooms) => {
  if (!publishClass.value && classrooms?.length) publishClass.value = classrooms[0].id;
}, { immediate: true, deep: true });
const dialogOpen = computed({
  get: () => !!modal.value,
  set: (value) => {
    if (!value) modal.value = "";
  },
});
function regenerate(id) {
  const original=store.data.lessonDraft.lessonSnapshot?.blocks?.find(b=>b.id===id);
  if(!original)return notify('此活动没有对应发布原稿，请直接编辑。');
  if(confirm('恢复此活动的发布原稿？其他活动保留。')){store.data.lessonDraft.blocks.find(b=>b.id===id).content=original.content;store.touch()}
}
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
function backupLocal(){const draft=store.data.lessonDraft;const text=[draft.goal,draft.studentBase,...draft.blocks.map(b=>b.title+'\n'+b.content),...draft.questions.map(q=>[q.prompt,q.equation,q.answer].join('\n'))].join('\n\n');const url=URL.createObjectURL(new Blob([text],{type:'text/plain;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='本地教案修改.txt';a.click();setTimeout(()=>URL.revokeObjectURL(url),500)}
async function reloadDraft(){if(!confirm('重新读取会替换当前未保存修改，请先下载本地修改。继续？'))return;store.externalUpdating=true;try{await store.load(store.data.lesson.id,true)}finally{store.externalUpdating=false}}
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
<p v-if="lessonSwitchBusy" role="status">读取课时教案…</p><template v-else>
  <PageHeading :title="store.data.lesson?.title || '我的教案'">
    <Button variant="outline" :disabled="store.saving" @click="saveDraft"><Save :size="16"/>{{ store.saving?'保存中…':'保存' }}</Button>
    <Button variant="outline" @click="workTab='preview'"><Eye :size="16"/>学生预览</Button>
    <Button @click="modal='publish'"><Send :size="16"/>发布任务</Button>
  </PageHeading>
  <div class="teacher-workbar">
    <AppTabs v-model="workTab" :items="[{value:'edit',label:'编辑教案'},{value:'preview',label:'学生预览'},{value:'references',label:'案例与版本'}]"/>
    <div class="teacher-workbar-actions">
      <RouteButton :route="'agent?lesson='+store.data.lesson?.id" secondary><WandSparkles :size="15"/>AI 备课</RouteButton>
      <Button variant="ghost" @click="moreOpen=true">更多操作</Button>
    </div>
  </div>
  <AppDialog v-model:open="moreOpen" title="教案操作"><div class="teacher-more-actions">
    <Button variant="outline" @click="workTab='references';moreOpen=false;tools?.history()">查看历史版本</Button>
    <Button variant="outline" @click="moreOpen=false;tools?.download()">导出 DOCX</Button>
    <Button variant="outline" :disabled="templateBusy" @click="applyPublished">使用发布课时内容</Button>
    <RouteButton route="courses" secondary>选择其他课时</RouteButton>
    <RouteButton route="teacher" secondary>返回教学概览</RouteButton>
  </div></AppDialog>
  <div v-if="store.saveError" class="preparation-conflict" role="alert"><p>{{ store.saveError }}</p><Button variant="outline" @click="backupLocal">下载本地修改</Button><Button @click="reloadDraft">重新读取</Button></div><section v-if="workTab==='edit'" class="teacher-editor-sheet"><div class="lesson-editor">
        <div class="editor-intro">
          <span><FileText :size="16" />教案草稿</span
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
        <details class="preparation-details"><summary>教学安排</summary><label v-for="(label,key) in {focus:'教学重点',difficulty:'教学难点',teacherQuestions:'教师提问',studentResponses:'学生可能回应',adjustments:'教师调整'}" :key="key">{{ label }}<Textarea v-model="details[key]"/></label></details><div class="editor-section-heading">
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
            ><details class="editor-block teacher-activity" :open="index===0"><summary><span class="teacher-activity-number">{{ String(index+1).padStart(2,'0') }}</span><strong>{{ block.title }}</strong></summary>
              <div class="editor-block-heading">
                <button
                  class="drag-handle"
                  :aria-label="`拖动排序：${block.title}`"
                  @keydown="reorderKeyboard($event, index)"
                >
                  <GripVertical :size="16" />
                </button>
                <Input v-model="block.title" :aria-label="'活动标题'+(index+1)"/>
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
              /><details v-if="block.studentContent!==undefined||block.agentJobId" class="preparation-block-notes" @toggle="$event.target.open&&ensureStudentCopy(block)"><summary>学生正文</summary><label>学生标题<Input v-model="block.studentTitle" :aria-label="'学生标题'+(index+1)"/></label><label>学生正文<Textarea v-model="block.studentContent" :aria-label="'学生正文'+(index+1)"/></label></details><details class="preparation-block-notes"><summary>提问与调整</summary><label v-for="(label,key) in {teacherQuestion:'教师提问',studentResponse:'学生可能回应',adjustment:'调整建议'}" :key="key">{{ label }}<Textarea v-model="block[key]"/></label></details><RouteButton :route="'agent?lesson='+store.data.lesson?.id+'&block='+block.id" secondary>AI 改写此活动</RouteButton></details></template></draggable
        ><details class="curriculum-teacher-questions"><summary>编辑题目 · {{ store.data.lessonDraft.questions?.length||0 }}</summary><div v-for="q in store.data.lessonDraft.questions" :key="q.id||q.equation"><label v-for="(label,key) in {prompt:'题干',equation:'方程',answer:'参考答案',hint:'提示'}" :key="key">{{ label }}<Input v-model="q[key]"/></label></div></details><button class="reference-link" @click="navigate(caseRoute)" :disabled="!store.data.lessonDraft.caseId">
          <LibraryBig :size="16" /><span>参考案例 · {{ caseReference?.title || '尚未选择' }}</span
          ><ArrowUpRight :size="15" />
        </button></div></section>
      <section v-else-if="workTab==='preview'" class="teacher-student-preview"><LessonPreview/></section>
      <section v-show="workTab==='references'" class="teacher-reference-sheet"><PreparationTools ref="tools"/><details class="teacher-source-detail"><summary>当前主要参考 · {{ caseReference?.title || '尚未选择' }}</summary><p v-if="referenceError" class="form-error">{{ referenceError }}</p><CaseArticle v-if="caseReference" :value="caseReference"/><RouteButton v-if="store.data.lessonDraft.caseId" :route="caseRoute" secondary>阅读完整案例</RouteButton></details></section>
  <AppDialog
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
        >截止日期（北京时间）</label
      ><Input
        id="due-date"
        v-model="store.data.lessonDraft.dueDate"
        type="date" />
      <p class="small-caption">发布后，所选班级的学生将收到本次教案的固定版本；后续编辑不改变本次任务。</p>
      <Button @click="publish" :disabled="store.publishing || !store.data.classrooms.length"
        >{{ store.publishing ? "发布中…" : "确认发布"
        }}<ArrowRight /></Button></template
  ></AppDialog>
</template>
</template>
