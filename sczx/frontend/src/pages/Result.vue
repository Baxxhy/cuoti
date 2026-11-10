<script setup>
import SupplementPanel from "@/components/SupplementPanel.vue";
import { inject, ref } from "vue";
import { useLearning } from "@/store.js";
import { navigate } from "@/lib/navigation.js";
import TaskEmpty from "@/components/TaskEmpty.vue";
import { ArrowRight, CheckCircle2, ChevronRight } from "lucide-vue-next";
const store = useLearning(),
  notify = inject("notify");
const submitting = ref(false);
async function submitResult() {
  if (submitting.value) return;
  submitting.value = true;
  try {
    await store.submitLesson();
    notify("本课结果已提交给教师");
  } catch (error) {
    notify(error.message);
  } finally {
    submitting.value = false;
  }
}
</script>
<template>
  <template v-if="store.task"
    ><PageHeading title="本课结果"
      ><RouteButton route="learn" secondary>返回本课</RouteButton></PageHeading
    >
    <div class="result-banner">
      <span><CheckCircle2 :size="32" :stroke-width="1.4" /></span>
      <div>
        <h2>{{ store.record.completed ? "已提交" : "待提交" }}</h2>
      </div>
      <Button
        @click="submitResult"
        :disabled="submitting||store.task.readOnly"
        >{{ submitting ? "提交中…" : store.record.completed ? "再次提交结果" : "提交本课结果"
        }}<ArrowRight
      /></Button>
    </div>
    <div class="two-column">
      <Surface
        ><SectionHeading title="本次学习记录" /><button
          v-for="item in [
            {
              title: '检查题尝试',
              text: `${store.record.attempts.length} 次作答，原答案和解释均已记录`,
              route: 'records',
            },
            {
              title: '独立应用',
              text: `${store.record.attempts.filter((i) => i.correct && !i.helped && store.task.questions[i.question]?.kind!=='practice').length} 次未使用帮助且数值正确`,
              route: 'check',
            },
            {
              title: '错题补救',
              text: store.record.repairs.some((item) => item.correct)
                ? '已完成一次变式尝试'
                : '还可以回看等式两边的共同变化',
              route: 'repair',
            },
          ]"
          :key="item.title"
          class="result-row"
          @click="navigate(item.route)"
        >
          <CheckCircle2 :size="18" /><span
            ><strong>{{ item.title }}</strong
            ><small>{{ item.text }}</small></span
          ><ChevronRight :size="17" /></button></Surface
      ><Surface class="teacher-feedback"
        ><div class="feedback-avatar">
          <span>师</span>
          <h3>教师的反馈</h3>
        </div>
        <blockquote>
          {{ store.record.feedback || "教师反馈将在保存后显示。" }}
        </blockquote>
        <RouteButton route="check" secondary>继续检查新题</RouteButton></Surface
      >
    </div><SupplementPanel :task-id="store.task.id"/></template
  ><TaskEmpty v-else />
</template>
