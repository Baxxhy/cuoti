<script setup>
import MemoryBridge from "@/components/MemoryBridge.vue";
import { ref, computed, onMounted, watch, onBeforeUnmount } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useLearning } from "@/store.js";
import { teachingApi, deadlineText } from "@/services/teaching.js";
import TaskList from "@/components/TaskList.vue";
import MessageCenter from "@/components/MessageCenter.vue";
import { ArrowRight, Users, BookOpen, Inbox } from "lucide-vue-next";
const taskTab=ref("pending");
const store = useLearning(),
  route = useRoute(),
  router = useRouter(),
  teacher = computed(() => route.name === "teacher"),
  overview = ref(null),
  error = ref(""),
  loading = ref(true),
  selected = ref(
    String(
      route.query.class ||
        store.currentClassId ||
        store.data.classroom?.id ||
        "",
    ),
  );
let generation = 0;
async function load() {
  const g = ++generation;
  loading.value = true;
  error.value = "";
  overview.value = null;
  try {
    const value = await teachingApi.dashboard(
      teacher.value ? selected.value : undefined,
    );
    if (g !== generation) return;
    overview.value = value;
    if (teacher.value) {
      selected.value = value.selectedClassId || "";
      store.currentClassId = selected.value;
      store.data.publishClassId = selected.value;
    }
  } catch (e) {
    if (g === generation) error.value = e.message;
  } finally {
    if (g === generation) loading.value = false;
  }
}
watch(
  () => route.query.class,
  (id) => {
    if (teacher.value && id && id !== selected.value) {
      selected.value = String(id);
      load();
    }
  },
);
onMounted(load);
async function select() {
  await router.replace({
    query: { ...route.query, class: selected.value || undefined },
  });
  load();
}
onBeforeUnmount(() => {
  generation++;
});
const pendingTasks=computed(()=>(overview.value?.tasks||[]).filter(t=>!["已提交","已反馈","历史只读"].includes(t.status)));
const nextTask=computed(()=>pendingTasks.value[0]);
const nextHasReading=computed(()=>!!(store.data.tasks.find(t=>t.id===nextTask.value?.id)?.snapshot?.blocks?.length));
const visibleTasks=computed(()=>teacher.value?overview.value?.tasks||[]:taskTab.value==='pending'?pendingTasks.value:(overview.value?.tasks||[]).filter(t=>!pendingTasks.value.includes(t)));
const metrics=computed(()=>teacher.value?[['班级任务',overview.value?.stats.tasks||0],['未提交',overview.value?.stats.unsubmittedStudents||0],['待反馈',overview.value?.stats.waitingFeedback||0]]:[['待完成',overview.value?.stats.pending||0],['学习中',overview.value?.stats.inProgress||0],['已提交',overview.value?.stats.submitted||0]]);
</script>
<template>
  <PageHeading :title="teacher?'教学概览':'我的学习'">
    <AppSelect v-if="teacher && overview?.classes.length" v-model="selected" label="当前班级" :options="overview.classes.map(c=>({value:c.id,label:c.name}))" @update:model-value="select"/>
  </PageHeading>
  <div v-if="error" class="form-error" role="alert">{{error}}<Button variant="outline" @click="load">重试</Button></div>
  <div v-if="loading" class="workspace-loading" role="status"><span/>正在读取任务…</div>
  <template v-if="overview">
    <section class="overview-next" aria-labelledby="next-task-heading">
      <div class="overview-next-copy">
        <span class="overview-context">{{teacher?'下一节课':nextTask?'待完成任务':'课程学习'}}</span>
        <h2 id="next-task-heading">{{teacher?store.data.lessonDraft?.title||store.data.lesson?.title||'准备一节新课':nextTask?.title||'开始你的下一课'}}</h2>
        <span class="overview-class" v-if="teacher">{{overview.classes.find(c=>c.id===selected)?.name||'尚未选择班级'}}</span>
        <span class="overview-class" v-else-if="nextTask">{{nextTask.className||'我的班级'}}</span>
        <div class="overview-next-actions"><RouteButton :route="teacher?'prepare'+(selected?'?class='+selected:''):nextTask?(nextHasReading?'learn':'check')+'?task='+nextTask.id:'courses'">{{teacher?'继续备课':nextTask?(nextHasReading?(nextTask.status==='学习中'?'继续学习':'开始学习'):'开始练习'):'浏览课程'}}<ArrowRight :size="16"/></RouteButton><a v-if="teacher" :href="'#/insights?class='+selected" class="text-link">查看班级学情</a><a v-else href="#/courses" class="text-link">全部课程</a></div>
      </div>
      <dl class="overview-counts"><div v-for="[label,value] in metrics" :key="label"><dt>{{label}}</dt><dd>{{value}}</dd></div></dl>
    </section>
    <div class="overview-grid">
      <section class="overview-task-panel">
        <div class="section-heading"><h2>{{teacher?'班级任务':'学习任务'}}</h2><a href="#/class" class="text-link">{{teacher?'管理班级':'我的班级'}}<ArrowRight :size="14"/></a></div>
        <AppTabs v-if="!teacher" v-model="taskTab" :items="[{value:'pending',label:'待完成'},{value:'completed',label:'已提交'}]"/>
        <TaskList :teacher="teacher" :tasks="visibleTasks" :empty-label="!teacher?(taskTab==='completed'?'还没有已提交的任务':'当前任务已完成'):undefined"/>
        <section v-if="teacher" class="overview-recent"><div class="section-heading"><h2>最近提交</h2></div><article v-for="item in overview.recentSubmissions.slice(0,5)" :key="item.recordId"><span><strong>{{item.studentName}}</strong><small>{{item.taskTitle}}</small></span><time>{{deadlineText(item.submittedAt)}}</time><RouteButton :route="'insights?task='+item.taskId" secondary>查看</RouteButton></article><p v-if="!overview.recentSubmissions.length" class="muted">还没有学生提交</p></section>
      </section>
      <aside class="overview-aside">
        <section class="overview-shortcuts"><h2>{{teacher?'教学工作':'学习工具'}}</h2><a :href="teacher?'#/cases':'#/wrong'"><component :is="teacher?BookOpen:Inbox" :size="18"/><span>{{teacher?'查找教学案例':'整理错题'}}</span><ArrowRight :size="15"/></a><a :href="teacher?'#/exam-papers':'#/exams'"><BookOpen :size="18"/><span>{{teacher?'组卷与考试':'我的考试'}}</span><ArrowRight :size="15"/></a><a href="#/live"><Users :size="18"/><span>{{teacher?'开展实时课堂':'进入课堂'}}</span><ArrowRight :size="15"/></a></section>
        <section class="overview-inbox"><h2>消息与反馈<span v-if="store.unreadCount">{{store.unreadCount}}</span></h2><MessageCenter compact/></section>
        <MemoryBridge v-if="!teacher" compact/>
      </aside>
    </div>
  </template>
</template>
