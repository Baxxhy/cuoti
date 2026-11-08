<script setup>
import {ref,onMounted,computed} from 'vue';
import {curriculumApi} from '@/services/curriculum.js';
import {useLearning} from '@/store.js';
import {navigate} from '@/lib/navigation.js';
import LessonPreview from '@/components/LessonPreview.vue';
import {BookOpen,Clock,ArrowUpRight} from 'lucide-vue-next';
const store=useLearning();const courses=ref([]),error=ref(''),loading=ref(true),preview=ref(null),busy=ref(false);
const teacher=computed(()=>store.user?.role==='teacher');
async function load(){loading.value=true;error.value='';try{courses.value=await curriculumApi.catalog()}catch(e){error.value=e.message}finally{loading.value=false}}
function taskFor(id){return store.data.tasks.find(t=>t.lessonId===id)}
async function prepare(lesson){busy.value=true;error.value='';try{await store.selectLesson(lesson.id);navigate('prepare?lesson='+lesson.id)}catch(e){error.value=e.message}finally{busy.value=false}}
onMounted(load);
</script>
<template><PageHeading :title="teacher?'课程与课时':'课程'"/><p v-if="error" class="form-error" role="alert">{{ error }}<Button variant="ghost" @click="load">重试</Button></p><p v-if="loading" role="status">读取中…</p><div v-else-if="!courses.length" class="empty-state"><BookOpen :size="30"/><h3>暂无已发布课程</h3></div><div class="curriculum-catalog"><section v-for="course in courses" :key="course.id" class="curriculum-course"><header><div class="curriculum-cover"><img src="/images/equation-balance.png" alt="数学课程插画"/></div><div><Status tone="blue">{{ course.grade }}</Status><h2>{{ course.title }}</h2><p>{{ course.units.length }} 个单元 · {{ course.units.reduce((n,u)=>n+u.lessons.length,0) }} 个已发布课时</p></div></header><div class="curriculum-unit" v-for="unit in course.units" :key="unit.id"><h3 v-if="unit.title!==course.title">{{ unit.title }}</h3><div class="curriculum-catalog-lessons"><Surface v-for="(lesson,i) in unit.lessons" :key="lesson.id"><div class="curriculum-catalog-number">{{ String(i+1).padStart(2,'0') }}</div><div class="curriculum-catalog-info"><h4>{{ lesson.published.title }}</h4><p>{{ lesson.published.goal }}</p><span><Clock :size="14"/>{{ lesson.published.duration }} 分钟<Status>v{{ lesson.published.version }}</Status></span></div><div class="curriculum-catalog-actions"><Button variant="ghost" @click="preview=lesson.published">预览课时</Button><Button v-if="teacher" :disabled="busy" @click="prepare(lesson)">进入备课<ArrowUpRight :size="16"/></Button><RouteButton v-else-if="taskFor(lesson.id)" :route="'learn?task='+taskFor(lesson.id).id">进入任务</RouteButton><Status v-else>尚无本课任务</Status></div></Surface></div></div></section></div><AppDialog :open="!!preview" @update:open="!$event&&(preview=null)" title="课时预览" content-class="library-preview"><LessonPreview v-if="preview" :lesson="preview"/></AppDialog></template>
