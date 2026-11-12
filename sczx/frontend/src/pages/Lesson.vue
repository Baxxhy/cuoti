<script setup>
import {computed,ref,inject,watch,nextTick} from 'vue';
import {ChevronLeft,ChevronRight,List,MessageCircle,MoreHorizontal} from '@/components/app/icons.js';
import {useLearning} from '@/store.js';
import {navigate} from '@/lib/navigation.js';
import LessonOutline from '@/components/LessonOutline.vue';
import LessonContent from '@/components/LessonContent.vue';
import QuestionAttempt from '@/components/QuestionAttempt.vue';
import ModelAssistant from '@/components/ModelAssistant.vue';
import MemoryReturn from '@/components/MemoryReturn.vue';
import MemoryBridge from '@/components/MemoryBridge.vue';
import UnitJourney from '@/components/UnitJourney.vue';
import SupplementPanel from '@/components/SupplementPanel.vue';
import TaskEmpty from '@/components/TaskEmpty.vue';
const store=useLearning(),notify=inject('notify',()=>{});
const selectedBlock=ref(null),selectedQuestion=ref(null),outlineOpen=ref(false),helpOpen=ref(false),moreOpen=ref(false),saving=ref(false);
const lesson=computed(()=>({...store.task?.snapshot,title:store.task?.title,questions:store.task?.questions||[]}));
const blocks=computed(()=>lesson.value.blocks||[]);
const blockIndex=computed(()=>Math.max(0,blocks.value.findIndex(b=>b.id===selectedBlock.value)));
const current=computed(()=>blocks.value[blockIndex.value]);
const currentQuestions=computed(()=>lesson.value.questions.map((q,index)=>({...q,index})).filter(q=>current.value?.questionIds?.includes(q.id)));
const questionPosition=computed(()=>Math.max(0,currentQuestions.value.findIndex(q=>q.index===selectedQuestion.value)));
const hasNextQuestion=computed(()=>current.value?.type==='practice'&&questionPosition.value<currentQuestions.value.length-1);
const progress=computed(()=>{
 const values={...store.record?.drafts.blocks};
 for(const block of blocks.value)if(['practice','check'].includes(block.type)){
  const attempted=new Set((store.record?.attempts||[]).map(a=>lesson.value.questions[a.question]?.id));
  values[block.id]={completed:!!block.questionIds?.length&&block.questionIds.every(id=>attempted.has(id))};
 }
 return values;
});
const canContinue=computed(()=>{
 if(store.task?.readOnly||!current.value)return true;
 if(current.value.type==='activity'){const p=progress.value[current.value.id];return !!(p?.weight>0&&p?.explanation?.trim())}
 if(current.value.type==='practice'&&currentQuestions.value.length)return !!store.record?.attempts.some(a=>a.question===selectedQuestion.value);
 return true;
});
function persistPosition(){
 if(!store.record||store.task?.readOnly)return;
 store.record.drafts.lessonPosition={blockId:selectedBlock.value,question:selectedQuestion.value};store.touch();
}
function selectBlock(id,question){
 const changed=id!==selectedBlock.value;selectedBlock.value=id;
 if(question!==undefined)selectedQuestion.value=question;
 else if(changed){const block=blocks.value.find(b=>b.id===id);selectedQuestion.value=lesson.value.questions.findIndex(q=>block?.questionIds?.includes(q.id));if(selectedQuestion.value<0)selectedQuestion.value=null}
 persistPosition();
}
watch([()=>store.task?.id,()=>store.record?.id,()=>blocks.value.map(b=>b.id).join('|')],()=>{
 const position=store.record?.drafts.lessonPosition;
 selectedBlock.value=blocks.value.some(b=>b.id===position?.blockId)?position.blockId:blocks.value[0]?.id||null;
 const candidates=lesson.value.questions.map((q,index)=>({...q,index})).filter(q=>current.value?.questionIds?.includes(q.id));
 selectedQuestion.value=candidates.some(q=>q.index===position?.question)?position.question:candidates[0]?.index??null;
 outlineOpen.value=false;helpOpen.value=false;
},{immediate:true,flush:'sync'});
watch(selectedBlock,async()=>{await nextTick();document.querySelector('.lesson-step-content')?.scrollTo({top:0});document.querySelector('.lesson-step-stage .curriculum-block-heading h2')?.focus({preventScroll:true});});
function update(id,value){
 if(!store.record||store.task?.readOnly)return;
 store.record.drafts.blocks||={};store.record.drafts.blocks[id]=value;
 store.record.observation=Object.values(store.record.drafts.blocks).map(b=>b.explanation).filter(Boolean).join('\n');store.touch();
}
function forward(){
 if(!current.value||!canContinue.value)return;
 if(hasNextQuestion.value){selectedQuestion.value=currentQuestions.value[questionPosition.value+1].index;persistPosition();return}
 if(['explanation','example','activity'].includes(current.value.type))update(current.value.id,{...progress.value[current.value.id],completed:true});
 if(blockIndex.value<blocks.value.length-1)selectBlock(blocks.value[blockIndex.value+1].id);
 else navigate('check?task='+store.task.id);
}
function back(){
 if(current.value?.type==='practice'&&questionPosition.value>0){selectedQuestion.value=currentQuestions.value[questionPosition.value-1].index;persistPosition()}
 else if(blockIndex.value>0)selectBlock(blocks.value[blockIndex.value-1].id);
}
function guide(index){if(index!==undefined)selectedQuestion.value=index;persistPosition();helpOpen.value=true;}
function locate(id){selectBlock(id);outlineOpen.value=false;}
async function save(){saving.value=true;notify(await store.save()?'学习进度已保存':store.saveError);saving.value=false;}
</script>
<template>
 <MemoryReturn/>
 <template v-if="store.task">
  <div class="lesson-focus-heading"><h1>{{store.task.title}}</h1><div><AppButton variant="ghost" size="sm" @click="moreOpen=true" aria-label="更多学习操作"><MoreHorizontal :size="18"/></AppButton></div></div>
  <template v-if="current">
   <div class="lesson-step-toolbar"><AppButton variant="ghost" @click="outlineOpen=true"><List :size="16"/>目录<span class="step-counter">{{blockIndex+1}} / {{blocks.length}}</span></AppButton><div class="lesson-step-track" aria-label="课时进度"><span v-for="(block,i) in blocks" :key="block.id" :class="{current:i===blockIndex,done:progress[block.id]?.completed}"/></div><InfoTip label="学习目标">{{lesson.goal}}</InfoTip></div>
   <AppAlert  v-if="store.task.readOnly" class="inline-notice" data-status="neutral">已移出班级，此任务仅可回看。</AppAlert>
   <div class="lesson-desktop-workbench"><aside class="lesson-desktop-outline"><h2>本课目录</h2><LessonOutline :lesson="lesson" :blocks="blocks" :progress="progress" :selected="selectedBlock" @select="locate"/></aside><div class="lesson-current-step"><section class="lesson-step-stage"><div class="lesson-step-content"><fieldset class="history-fields" :disabled="store.task.readOnly"><LessonContent :lesson="lesson" :progress="progress" focused :active-block-id="current.id" :question-index="selectedQuestion" @progress="update" @focus="selectBlock"><template #question="{question,index}"><QuestionAttempt :key="store.task.id+':'+question.id" :question="question" :index="index" @guide="guide"/></template></LessonContent></fieldset></div>
    <footer class="lesson-step-footer"><AppButton variant="ghost" :disabled="blockIndex===0&&questionPosition===0" @click="back"><ChevronLeft :size="16"/>上一步</AppButton><span v-if="store.saving" class="step-save-state" role="status">保存中…</span><span v-else-if="current.type==='practice'&&currentQuestions.length>1" class="step-question-count" role="status">{{questionPosition+1}} / {{currentQuestions.length}} 题</span><AppButton v-if="current.type==='check'" @click="navigate('check?task='+store.task.id)">开始练习<ChevronRight :size="16"/></AppButton><AppButton v-else :disabled="!canContinue" @click="forward">{{hasNextQuestion?'下一题':blockIndex===blocks.length-1?'开始练习':'下一步'}}<ChevronRight :size="16"/></AppButton></footer>
   </section>
   <div class="lesson-step-utility"><AppButton variant="ghost" @click="guide()"><MessageCircle :size="17"/>问一问</AppButton><span v-if="current.type==='activity'&&!canContinue" class="muted">完成互动并写下观察</span></div>
   </div></div>
   <AppDialog v-model:open="outlineOpen" title="本课目录" content-class="step-outline-dialog"><LessonOutline :lesson="lesson" :blocks="blocks" :progress="progress" :selected="selectedBlock" @select="locate"/></AppDialog>
   <AppDialog v-model:open="helpOpen" title="学习助手" content-class="step-help-dialog"><ModelAssistant v-if="helpOpen" :key="store.task.id" :question="selectedQuestion" :block-id="selectedBlock" :show-heading="false"/></AppDialog>
  </template>
  <section v-else class="student-practice-task"><template v-if="lesson.questions.length"><div class="section-heading"><h2>本次练习</h2><span>{{lesson.questions.length}} 题</span></div><ol class="student-practice-preview"><li v-for="(question,i) in lesson.questions.slice(0,1)" :key="question.id||i"><span>{{String(i+1).padStart(2,'0')}}</span><div><strong>{{question.prompt}}</strong><p v-if="question.equation" class="math-equation">{{question.equation}}</p></div></li></ol><RouteButton :route="'check?task='+store.task.id">开始独立练习</RouteButton></template><template v-else><p>本任务没有练习题。</p><RouteButton :route="'result?task='+store.task.id">查看学习结果</RouteButton></template></section>
  <AppDialog v-model:open="moreOpen" title="学习记录与资料" content-class="step-more-dialog"><div class="action-row"><AppButton variant="outline" :disabled="saving||store.task.readOnly" @click="save">保存进度</AppButton><RouteButton :route="'result?task='+store.task.id" secondary>学习结果</RouteButton></div><details class="study-disclosure"><summary>教师补充内容</summary><SupplementPanel :task-id="store.task.id"/></details><details class="study-disclosure"><summary>复习与单元进度</summary><MemoryBridge :task="store.task" compact/><UnitJourney v-if="store.task.unitId||store.task.snapshot.lessonSnapshot?.unitId" :unit-id="store.task.unitId||store.task.snapshot.lessonSnapshot.unitId" :task="store.task" compact/></details></AppDialog>
 </template><TaskEmpty v-else/>
</template>
