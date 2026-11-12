<script setup>
import { confirmAction } from '@/lib/confirm-action.js';
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
} from "@/components/app/icons.js";
import draggable from "vuedraggable";
import PreparationTools from "@/components/PreparationTools.vue";
import LessonPreview from "@/components/LessonPreview.vue";
import CaseArticle from "@/components/CaseArticle.vue";
import { modelApi } from "@/services/models.js";
import { curriculumApi } from "@/services/curriculum.js";
import {useRoute,useRouter} from "vue-router";
const store = useLearning(),
  notify = inject("notify");

const tools=ref(null);
function ensureStudentCopy(block) {
  const source=store.data.lessonDraft.lessonSnapshot?.blocks?.find(item=>item.id===block.id)||block;
  if(block.studentTitle===undefined) block.studentTitle=source.studentTitle??source.title;
  if(block.studentContent===undefined) block.studentContent=source.studentContent??source.content;
}

const workTab=ref("edit"), moreOpen=ref(false);
const selectedActivity=ref(''),selectedQuestion=ref('');
const activeBlock=computed(()=>store.blocks.find(b=>b.id===selectedActivity.value)||store.blocks[0]);
const activeQuestion=computed(()=>store.data.lessonDraft.questions?.find(q=>q.id===selectedQuestion.value)||store.data.lessonDraft.questions?.[0]);
watch(()=>store.data.lesson?.id,()=>{selectedActivity.value='';selectedQuestion.value=''});

const details=computed(()=>store.data.lessonDraft.planningDetails|| (store.data.lessonDraft.planningDetails={}));
const route=useRoute(),router=useRouter();
watch(()=>route.query.class,id=>{if(id&&store.data.classrooms.some(c=>c.id===id))store.data.publishClassId=String(id)},{immediate:true});const templateBusy=ref(false),lessonSwitchBusy=ref(false);
watch(()=>route.query.lesson,async id=>{
 if(!id&&store.data.lesson?.id){router.replace({query:{...route.query,lesson:store.data.lesson.id}});return}
 if(id&&id!==store.data.lesson?.id){
  lessonSwitchBusy.value=true;
  try{await store.selectLesson(String(id))}catch(e){notify(e.message)}finally{lessonSwitchBusy.value=false}
 }
},{immediate:true});
async function applyPublished(){if(!await confirmAction('使用当前发布课时替换本教案的目标、活动、题目与引用？学生基础、截止日期和已有任务保留。'))return;templateBusy.value=true;const draft=store.data.lessonDraft,id=store.data.lesson.id;try{const data=await curriculumApi.lesson(id);if(store.data.lessonDraft!==draft||store.data.lesson.id!==id)return;Object.assign(draft,{lessonId:id,lessonSnapshot:data,goal:data.goal,blocks:structuredClone(data.blocks),questions:structuredClone(data.questions),caseId:data.caseId,caseSnapshot:data.caseSnapshot});store.touch();notify(await store.save()?'已使用发布课时内容':store.saveError)}catch(e){notify(e.message)}finally{templateBusy.value=false}}
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
async function regenerate(id) {
  const original=store.data.lessonDraft.lessonSnapshot?.blocks?.find(b=>b.id===id);
  if(!original)return notify('此活动没有对应发布原稿，请直接编辑。');
  if(await confirmAction('恢复此活动的发布原稿？其他活动保留。')){store.data.lessonDraft.blocks.find(b=>b.id===id).content=original.content;store.touch()}
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
async function reloadDraft(){if(!await confirmAction('重新读取会替换当前未保存修改，请先下载本地修改。继续？'))return;store.externalUpdating=true;try{await store.load(store.data.lesson.id,true)}finally{store.externalUpdating=false}}
async function saveDraft() {
  if (await store.save()) notify("教案已保存");
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
<ElSkeleton v-if="lessonSwitchBusy" animated :rows="3" aria-label="读取课时教案…"/><template v-else>
  <PageHeading :title="store.data.lesson?.title || '我的教案'">
    <AppButton variant="outline" :disabled="store.saving" @click="saveDraft"><Save :size="16"/>{{ store.saving?'保存中…':'保存' }}</AppButton>
    <AppButton @click="modal='publish'"><Send :size="16"/>发布任务</AppButton>
  </PageHeading>
  <div class="teacher-workbar">
    <AppTabs v-model="workTab" :items="[{value:'edit',label:'教学活动'},{value:'settings',label:'课时设置'},{value:'questions',label:'练习题'},{value:'preview',label:'学生预览'},{value:'references',label:'资料与版本'}]"/>
    <div class="teacher-workbar-actions">
      <AppButton variant="ghost" @click="moreOpen=true">更多操作</AppButton>
    </div>
  </div>
  <AppDialog v-model:open="moreOpen" title="教案操作"><div class="teacher-more-actions">
    <AppButton variant="outline" @click="workTab='references';moreOpen=false;tools?.history()">查看历史版本</AppButton>
    <AppButton variant="outline" @click="moreOpen=false;tools?.download()">导出 DOCX</AppButton>
    <AppButton variant="outline" :disabled="templateBusy" @click="applyPublished">使用发布课时内容</AppButton>
    <RouteButton route="courses" secondary>选择其他课时</RouteButton>
    <RouteButton route="teacher" secondary>返回教学概览</RouteButton>
  </div></AppDialog>
  <AppAlert type="error" v-if="store.saveError" class="preparation-conflict" role="alert"><p>{{ store.saveError }}</p><AppButton :disabled="store.saving" @click="saveDraft">重新保存</AppButton><AppButton variant="outline" @click="backupLocal">下载本地修改</AppButton><AppButton variant="ghost" @click="reloadDraft">重新读取</AppButton></AppAlert><section v-if="workTab==='edit'" class="focus-preparation">
    <aside class="focus-activity-list" aria-label="教学活动顺序">
      <draggable v-model="store.data.lessonDraft.blocks" item-key="id" handle=".drag-handle" :force-fallback="true" :fallback-on-body="true" :fallback-tolerance="3" :animation="0" @end="notify('活动顺序已更新')">
        <template #item="{element:block,index}"><div class="focus-activity-item" :class="{selected:activeBlock?.id===block.id}"><button class="drag-handle" :aria-label="'调整顺序：'+block.title" @keydown="reorderKeyboard($event,index)"><GripVertical :size="13"/></button><button :aria-current="activeBlock?.id===block.id?'step':undefined" @click="selectedActivity=block.id"><span>{{String(index+1).padStart(2,'0')}}</span><strong>{{block.title}}</strong></button></div></template>
      </draggable>
    </aside>
    <div v-if="activeBlock" class="focus-activity-editor lesson-editor" :key="activeBlock.id">
      <div class="focus-editor-toolbar"><Status>{{store.saving?'保存中':store.saveError?'保存失败':store.savedAt?'已保存':'草稿'}}</Status><AppButton size="icon-sm" variant="ghost" :aria-label="'恢复原稿：'+activeBlock.title" :disabled="busyBlock===activeBlock.id" @click="regenerate(activeBlock.id)"><WandSparkles :size="16"/></AppButton></div>
      <label class="field-label" for="activity-title">活动名称</label><Input id="activity-title" v-model="activeBlock.title"/>
      <label class="field-label" for="activity-content">课堂说明</label><Textarea id="activity-content" v-model="activeBlock.content" :disabled="busyBlock===activeBlock.id"/>
      <AppDisclosure v-if="activeBlock.studentContent!==undefined||activeBlock.agentJobId" class="preparation-block-notes" @change="$event&&ensureStudentCopy(activeBlock)"><template #title>学生正文</template><label>学生标题<Input v-model="activeBlock.studentTitle" aria-label="学生标题"/></label><label>学生正文<Textarea v-model="activeBlock.studentContent" aria-label="学生正文"/></label></AppDisclosure>
      <AppDisclosure class="preparation-block-notes"><template #title>提问与调整</template><label v-for="(label,key) in {teacherQuestion:'教师提问',studentResponse:'学生可能回应',adjustment:'调整建议'}" :key="key">{{label}}<Textarea v-model="activeBlock[key]"/></label></AppDisclosure>
      <div class="focus-editor-footer"><RouteButton :route="'agent?lesson='+store.data.lesson?.id+'&block='+activeBlock.id" secondary><WandSparkles :size="15"/>AI 改写此活动</RouteButton><AppButton variant="ghost" @click="workTab='preview'">学生预览<Eye :size="15"/></AppButton></div>
    </div>
    <AppEmpty v-else class="empty-state">当前教案没有活动</AppEmpty>
  </section>
  <section v-else-if="workTab==='settings'" class="focus-preparation-settings">
    <label class="field-label" for="lesson-goal">本课目标</label><Textarea id="lesson-goal" v-model="store.data.lessonDraft.goal"/>
    <label class="field-label" for="student-base">学生基础</label><Input id="student-base" v-model="store.data.lessonDraft.studentBase"/>
    <div class="focus-settings-pair"><label v-for="(label,key) in {focus:'教学重点',difficulty:'教学难点'}" :key="key">{{label}}<Textarea v-model="details[key]"/></label></div>
    <AppDisclosure class="ops-disclosure"><template #title>整课提问与调整</template><label v-for="(label,key) in {teacherQuestions:'教师提问',studentResponses:'学生可能回应',adjustments:'教师调整'}" :key="key">{{label}}<Textarea v-model="details[key]"/></label></AppDisclosure>
  </section>
  <section v-else-if="workTab==='questions'" class="focus-preparation">
    <aside class="focus-activity-list" aria-label="练习题"><button v-for="(q,index) in store.data.lessonDraft.questions" :key="q.id||q.equation" :class="['focus-question-choice',{selected:activeQuestion===q}]" :aria-current="activeQuestion===q?'step':undefined" @click="selectedQuestion=q.id"><span>{{String(index+1).padStart(2,'0')}}</span><strong>{{q.equation||q.prompt}}</strong></button></aside>
    <div v-if="activeQuestion" class="focus-activity-editor"><label v-for="(label,key) in {prompt:'题干',equation:'方程',answer:'参考答案',hint:'提示'}" :key="key" class="field-label">{{label}}<Textarea v-if="key==='hint'" v-model="activeQuestion[key]"/><Input v-else v-model="activeQuestion[key]"/></label></div><AppEmpty v-else class="empty-state">当前教案没有练习题</AppEmpty>
  </section>
      <section v-else-if="workTab==='preview'" class="teacher-student-preview"><LessonPreview/></section>
      <section v-show="workTab==='references'" class="teacher-reference-sheet"><PreparationTools ref="tools"/><AppDisclosure class="teacher-source-detail"><template #title>当前主要参考 　 {{ caseReference?.title || '尚未选择' }}</template><AppAlert type="error" v-if="referenceError" class="form-error">{{ referenceError }}</AppAlert><CaseArticle v-if="caseReference" :value="caseReference"/><RouteButton v-if="store.data.lessonDraft.caseId" :route="caseRoute" secondary>阅读完整案例</RouteButton></AppDisclosure></section>
  <AppDialog
    v-model:open="dialogOpen"
    :title="modal === 'preview' ? '学生预览' : '发布学习任务'"
    :content-class="
      modal === 'preview' ? 'lesson-preview-dialog' : 'publish-dialog'
    "
    ><template v-if="modal === 'preview'"
      ><LessonPreview /><AppButton @click="modal = 'publish'"
        >继续发布<ArrowRight /></AppButton></template
    ><template v-else
      ><AppAlert type="error" v-if="publishError" class="form-error" role="alert">{{ publishError }}</AppAlert>
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
        :options="store.data.classrooms.map((item) => ({ value: item.id, label: `${item.name} 　 ${item.grade}` }))" /><AppAlert type="error" v-if="!store.data.classrooms.length" class="form-error">先在班级教学中创建班级并添加学生。</AppAlert><label
        class="field-label"
        for="due-date"
        >截止日期（北京时间）</label
      ><Input
        id="due-date"
        v-model="store.data.lessonDraft.dueDate"
        type="date" />
      <p class="small-caption">发布后，所选班级的学生将收到本次教案的固定版本；后续编辑不改变本次任务。</p>
      <AppButton @click="publish" :disabled="store.publishing || !store.data.classrooms.length"
        >{{ store.publishing ? "发布中…" : "确认发布"
        }}<ArrowRight /></AppButton></template
  ></AppDialog>
</template>
</template>
