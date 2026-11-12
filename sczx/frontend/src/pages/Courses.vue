<script setup>
import {useEducation} from "@/services/education.js";
import {ElSelect,ElOption} from "element-plus";
import UnitJourney from "@/components/UnitJourney.vue";
import {ref,onMounted,computed} from 'vue';
import {curriculumApi} from '@/services/curriculum.js';
import {useLearning} from '@/store.js';
import {navigate} from '@/lib/navigation.js';
import LessonPreview from '@/components/LessonPreview.vue';
import {BookOpen,Clock,ArrowUpRight} from '@/components/app/icons.js';
const store=useLearning();const courses=ref([]),error=ref(''),loading=ref(true),preview=ref(null),busy=ref(false);
const {catalog:education}=useEducation();
const selectedGrade=ref(''),selectedSubject=ref('');
const visibleCourses=computed(()=>courses.value.filter(c=>(!selectedGrade.value||c.grade===selectedGrade.value)&&(!selectedSubject.value||c.metadata?.subject===selectedSubject.value)));
const teacher=computed(()=>store.user?.role==='teacher');
async function load(){loading.value=true;error.value='';try{courses.value=await curriculumApi.catalog()}catch(e){error.value=e.message}finally{loading.value=false}}
function taskFor(id){return store.data.tasks.find(t=>t.lessonId===id)}
async function prepare(lesson){busy.value=true;error.value='';try{await store.selectLesson(lesson.id);navigate('prepare?lesson='+lesson.id)}catch(e){error.value=e.message}finally{busy.value=false}}
onMounted(load);
</script>
<template>
  <PageHeading :title="teacher?'课程与课时':'课程'"/>
  <div class="course-filters"><ElSelect v-model="selectedGrade" clearable placeholder="全部年级" aria-label="筛选年级"><ElOption v-for="grade in education.stages.flatMap(s=>s.grades)" :key="grade" :value="grade" :label="grade"/></ElSelect><ElSelect v-model="selectedSubject" clearable filterable placeholder="全部学科" aria-label="筛选学科"><ElOption v-for="subject in [...new Set([...education.subjects.map(s=>s.value),...courses.map(c=>c.metadata?.subject).filter(Boolean)])]" :key="subject" :value="subject" :label="subject"/></ElSelect></div>
  <AppEmpty v-if="!loading&&!visibleCourses.length&&!error"><h3>当前学科暂无已发布课程</h3></AppEmpty>
  <AppAlert type="error" v-if="error" class="form-error" role="alert">{{ error }}<AppButton variant="ghost" @click="load">重试</AppButton></AppAlert>
  <ElSkeleton v-if="loading" animated :rows="3" aria-label="读取中…"/>
  <AppEmpty v-else-if="!courses.length" class="empty-state"><BookOpen :size="30"/><h3>暂无已发布课程</h3></AppEmpty>
  <div v-else class="student-catalog">
    <Surface data-ui="card" v-for="course in visibleCourses" :key="course.id" class="student-course">
      <ElSpace wrap :size="12" class="student-course-header">
        <BookOpen :size="25" :stroke-width="1.5"/>
        <div><h2>{{ course.title }}</h2><span>{{ course.grade }} 　 {{course.units.reduce((n,u)=>n+u.lessons.length,0)}} 课时</span></div>
      </ElSpace>
      <section v-for="unit in course.units" :key="unit.id" class="student-course-unit">
        <h3 v-if="unit.title!==course.title">{{unit.title}}</h3>
        <div class="student-lesson-list">
          <Surface data-ui="card" role="article" v-for="(lesson,i) in unit.lessons" :key="lesson.id" class="student-lesson-row">
            <span class="student-lesson-number">{{unit.hasPlan&&!unit.lessonOrder.includes(lesson.id)?'＋':String(i+1).padStart(2,'0')}}</span>
            <div class="student-lesson-name"><h3>{{lesson.published.title}}</h3><span>{{lesson.published.duration}} 分钟<span v-if="unit.hasPlan&&!unit.lessonOrder.includes(lesson.id)"> 　 补充课时</span></span></div>
            <div class="student-lesson-actions">
              <AppButton variant="ghost" @click="preview=lesson.published">预览</AppButton>
              <AppButton v-if="teacher" :disabled="busy" @click="prepare(lesson)">开始备课<ArrowUpRight :size="16"/></AppButton>
              <RouteButton v-else-if="taskFor(lesson.id)" :route="'learn?task='+taskFor(lesson.id).id">进入学习</RouteButton>
              <span v-else class="muted">未分配任务</span>
            </div>
          </Surface>
        </div>
        <AppDisclosure v-if="!teacher&&store.user?.role==='student'" class="study-disclosure"><template #title>单元进度</template><UnitJourney :unit-id="unit.id"/></AppDisclosure>
      </section>
    </Surface>
  </div>
  <AppDialog :open="!!preview" @update:open="!$event&&(preview=null)" title="课时预览" content-class="library-preview"><LessonPreview v-if="preview" :lesson="preview"/></AppDialog>
</template>
