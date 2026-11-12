<script setup>
import UnitJourney from "@/components/UnitJourney.vue";
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
<template>
  <PageHeading :title="teacher?'课程与课时':'课程'"/>
  <p v-if="error" class="form-error" role="alert">{{ error }}<Button variant="ghost" @click="load">重试</Button></p>
  <p v-if="loading" role="status">读取中…</p>
  <div v-else-if="!courses.length" class="empty-state"><BookOpen :size="30"/><h3>暂无已发布课程</h3></div>
  <div v-else class="student-catalog">
    <section v-for="course in courses" :key="course.id" class="student-course">
      <header class="student-course-header">
        <BookOpen :size="25" :stroke-width="1.5"/>
        <div><h2>{{ course.title }}</h2><span>{{ course.grade }} 　 {{course.units.reduce((n,u)=>n+u.lessons.length,0)}} 课时</span></div>
      </header>
      <section v-for="unit in course.units" :key="unit.id" class="student-course-unit">
        <h3 v-if="unit.title!==course.title">{{unit.title}}</h3>
        <div class="student-lesson-list">
          <article v-for="(lesson,i) in unit.lessons" :key="lesson.id" class="student-lesson-row">
            <span class="student-lesson-number">{{unit.hasPlan&&!unit.lessonOrder.includes(lesson.id)?'＋':String(i+1).padStart(2,'0')}}</span>
            <div class="student-lesson-name"><h3>{{lesson.published.title}}</h3><span>{{lesson.published.duration}} 分钟<span v-if="unit.hasPlan&&!unit.lessonOrder.includes(lesson.id)"> 　 补充课时</span></span></div>
            <div class="student-lesson-actions">
              <Button variant="ghost" @click="preview=lesson.published">预览</Button>
              <Button v-if="teacher" :disabled="busy" @click="prepare(lesson)">开始备课<ArrowUpRight :size="16"/></Button>
              <RouteButton v-else-if="taskFor(lesson.id)" :route="'learn?task='+taskFor(lesson.id).id">进入学习</RouteButton>
              <span v-else class="muted">未分配任务</span>
            </div>
          </article>
        </div>
        <details v-if="!teacher&&store.user?.role==='student'" class="study-disclosure"><summary>单元进度</summary><UnitJourney :unit-id="unit.id"/></details>
      </section>
    </section>
  </div>
  <AppDialog :open="!!preview" @update:open="!$event&&(preview=null)" title="课时预览" content-class="library-preview"><LessonPreview v-if="preview" :lesson="preview"/></AppDialog>
</template>
