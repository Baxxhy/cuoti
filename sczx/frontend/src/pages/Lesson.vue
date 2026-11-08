<script setup>
import {computed,ref,inject} from 'vue';
import {CheckCircle2,ChevronRight} from 'lucide-vue-next';
import {useLearning} from '@/store.js';
import Workspace from '@/components/Workspace.vue';
import LessonContent from '@/components/LessonContent.vue';
import QuestionAttempt from '@/components/QuestionAttempt.vue';
import ModelAssistant from '@/components/ModelAssistant.vue';
import TaskEmpty from '@/components/TaskEmpty.vue';
const store=useLearning(),notify=inject('notify');const saving=ref(false);
const lesson=computed(()=>({...store.task?.snapshot,title:store.task?.title,questions:store.task?.questions||[]}));
const progress=computed(()=>{const values={...store.record?.drafts.blocks};for(const block of store.task?.snapshot.blocks||[]){if(['practice','check'].includes(block.type)){const ids=new Set((store.record?.attempts||[]).map(a=>store.task.questions[a.question]?.id));values[block.id]={completed:!!block.questionIds?.length&&block.questionIds.every(id=>ids.has(id))}}}return values});
const completed=computed(()=>Object.values(progress.value).filter(v=>v.completed).length);
function update(id,value){if(!store.record)return;store.record.drafts.blocks||={};store.record.drafts.blocks[id]=value;store.record.observation=Object.values(store.record.drafts.blocks).map(b=>b.explanation).filter(Boolean).join('\n');store.touch()}
function locate(id){document.querySelector(`[data-block="${CSS.escape(id)}"]`)?.scrollIntoView({block:"start",behavior:window.matchMedia("(prefers-reduced-motion: reduce)").matches?"auto":"smooth"})}
async function save(){saving.value=true;notify(await store.save()?'学习进度已保存':store.saveError);saving.value=false}
</script>
<template><template v-if="store.task"><PageHeading :title="store.task.title"><Button variant="outline" :disabled="saving" @click="save">{{ saving?'保存中…':'保存进度' }}</Button><RouteButton route="check">独立检查</RouteButton><RouteButton route="result" secondary>学习结果</RouteButton></PageHeading><div class="curriculum-study-meta"><span>{{ store.task.snapshot.lessonSnapshot?.grade||'课程学习' }}</span><span>{{ completed }} / {{ lesson.blocks?.length||0 }} 个内容块已标记</span><Status v-if="store.task.snapshot.lessonSnapshot">v{{ store.task.snapshot.lessonSnapshot.version }}</Status></div><Workspace><template #primary><LessonContent :lesson="lesson" :progress="progress" @progress="update"><template #question="{question,index,block}"><QuestionAttempt v-if="block.type==='practice'" :key="question.id" :question="question" :index="index"/><RouteButton v-else route="check" secondary>进入独立检查</RouteButton></template></LessonContent></template><template #secondary><nav class="curriculum-outline" aria-label="本课内容"><div class="library-pane-heading"><h2>本课内容</h2><InfoTip label="内容来源">{{ store.task.snapshot.lessonSnapshot?.source||'历史任务内容，版本来源未记录' }}</InfoTip></div><button v-for="(block,i) in lesson.blocks" :key="block.id" @click="locate(block.id)"><span>{{ String(i+1).padStart(2,'0') }}</span><strong>{{ block.title }}</strong><CheckCircle2 v-if="progress[block.id]?.completed" :size="16"/><ChevronRight v-else :size="16"/></button></nav><ModelAssistant/></template></Workspace></template><TaskEmpty v-else/></template>
