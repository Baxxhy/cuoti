<script setup>
import {computed,ref,watch} from 'vue';
import {ChevronLeft,ChevronRight} from '@/components/app/icons.js';
import {useLearning} from '@/store.js';
import LessonContent from './LessonContent.vue';
import QuestionAttempt from './QuestionAttempt.vue';
import {readingValue} from '@/lib/lesson-reading.js';
const props=defineProps({lesson:Object});const store=useLearning(),progress=ref({}),index=ref(0),question=ref(0),outline=ref(false);
const content=computed(()=>props.lesson||{...store.data.lessonDraft,title:store.data.lesson?.title||'课时预览'});
const blocks=computed(()=>content.value.blocks||[]),current=computed(()=>blocks.value[index.value]);
const questions=computed(()=>(content.value.questions||[]).map((q,index)=>({...q,index})).filter(q=>current.value?.questionIds?.includes(q.id)));
watch(()=>content.value.lessonId,()=>{progress.value={};index.value=0});watch(index,()=>question.value=0);
function update(id,value){progress.value={...progress.value,[id]:value}}
function next(){if(current.value?.type==='practice'&&question.value<questions.value.length-1)question.value++;else if(index.value<blocks.value.length-1)index.value++}
</script>
<template><div class="student-preview student-step-preview"><div class="preview-step-header"><h2>{{content.title}}</h2><AppButton variant="ghost" size="sm" @click="outline=!outline">目录 {{index+1}} / {{blocks.length}}</AppButton></div><nav v-if="outline" class="preview-step-directory" aria-label="预览目录"><button v-for="(block,n) in blocks" :key="block.id" :aria-current="n===index?'step':undefined" @click="index=n;outline=false">{{n+1}}　{{readingValue(content,block,'title')}}</button></nav><LessonContent v-if="current" :lesson="content" :progress="progress" preview focused :active-block-id="current.id" :question-index="questions[question]?.index??null" @progress="update"><template #question="{question:currentQuestion,index:questionIndex}"><QuestionAttempt :key="currentQuestion.id" :question="currentQuestion" :index="questionIndex" preview/></template></LessonContent><p v-else>暂无课时内容</p><div v-if="current" class="lesson-step-footer"><AppButton variant="ghost" :disabled="index===0" @click="index--"><ChevronLeft :size="16"/>上一步</AppButton><AppButton :disabled="index===blocks.length-1&&!(current.type==='practice'&&question<questions.length-1)" @click="next">下一步<ChevronRight :size="16"/></AppButton></div></div></template>
