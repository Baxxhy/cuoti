<script setup>
import {computed,ref,watch} from 'vue';
import {useLearning} from '@/store.js';
import LessonContent from './LessonContent.vue';
import QuestionAttempt from './QuestionAttempt.vue';
const props=defineProps({lesson:Object});const store=useLearning();const progress=ref({});
const content=computed(()=>props.lesson||{...store.data.lessonDraft,title:store.data.lesson?.title||'课时预览'});
watch(()=>content.value.lessonId,()=>progress.value={});
function update(id,value){progress.value={...progress.value,[id]:value}}
</script>
<template><div class="student-preview"><LessonContent :lesson="content" :progress="progress" preview @progress="update"><template #question="{question,index}"><QuestionAttempt :key="question.id" :question="question" :index="index" preview/></template></LessonContent></div></template>
