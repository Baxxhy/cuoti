<script setup>
import UnitJourney from "@/components/UnitJourney.vue";
import MemoryReturn from "@/components/MemoryReturn.vue";
import SupplementPanel from "@/components/SupplementPanel.vue";
import { computed, inject, ref } from "vue";
import { useLearning } from "@/store.js";
import { navigate } from "@/lib/navigation.js";
import TaskEmpty from "@/components/TaskEmpty.vue";
import { ArrowRight, CheckCircle2, ChevronRight } from "lucide-vue-next";
const store = useLearning(),
  notify = inject("notify");
const submitting = ref(false), confirmOpen = ref(false);
const checkAttempts = computed(()=>(store.record?.attempts||[]).filter(a=>store.task?.questions[a.question]?.kind!=='practice'));
const independentCorrect = computed(()=>checkAttempts.value.filter(a=>a.correct&&!a.helped).length);
const repairCount = computed(()=>store.record?.repairs.length||0);
async function submitResult() {
  if (submitting.value) return;
  submitting.value = true;
  try {
    await store.submitLesson();
    confirmOpen.value=false;
    notify("本课结果已提交给教师");
  } catch (error) {
    notify(error.message);
  } finally {
    submitting.value = false;
  }
}
</script>
<template>
  <MemoryReturn/>
  <template v-if="store.task">
    <PageHeading title="学习结果"><RouteButton route="learn" secondary>返回本课</RouteButton></PageHeading>
    <section class="student-result-summary">
      <div><span class="student-result-task">{{store.task.title}}<InfoTip label="独立正确范围">未使用帮助且数值核验正确，不代表已经掌握。</InfoTip></span><h2>{{store.record.completed?'已提交给教师':'准备提交'}}</h2></div>
      <Button :disabled="submitting||store.task.readOnly" @click="confirmOpen=true">{{store.record.completed?'更新提交':'提交学习结果'}}<ArrowRight :size="16"/></Button>
    </section>
    <div class="student-result-metrics">
      <button @click="navigate('records')"><strong>{{checkAttempts.length}}</strong><span>检查题作答<ChevronRight :size="14"/></span></button>
      <button @click="navigate('check')"><strong>{{independentCorrect}}</strong><span>独立正确记录</span></button>
      <button @click="navigate('wrong')"><strong>{{repairCount}}</strong><span>补救练习<ChevronRight :size="14"/></span></button>
    </div>
    <Surface class="student-teacher-feedback"><SectionHeading title="教师反馈"/><p class="preserve-lines">{{store.record.feedback||'暂无反馈'}}</p></Surface>
    <details class="study-disclosure"><summary>教师补充内容</summary><SupplementPanel :task-id="store.task.id"/></details>
    <details v-if="store.task?.unitId||store.task?.snapshot.lessonSnapshot?.unitId" class="study-disclosure"><summary>单元进度</summary><UnitJourney :unit-id="store.task.unitId||store.task.snapshot.lessonSnapshot.unitId" :task="store.task" compact/></details>
    <AppDialog v-model:open="confirmOpen" title="提交学习结果"><p>教师将看到本课作答、求助和补救记录。</p><div class="action-row"><Button :disabled="submitting" @click="submitResult">{{submitting?'提交中…':'确认提交'}}</Button><Button variant="outline" :disabled="submitting" @click="confirmOpen=false">取消</Button></div></AppDialog>
  </template>
  <TaskEmpty v-else/>
</template>
