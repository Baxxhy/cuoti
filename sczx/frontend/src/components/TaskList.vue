<script setup>
import { computed } from "vue";
import { deadlineText } from "@/services/teaching.js";
import { useLearning } from "@/store.js";
import { navigate } from "@/lib/navigation.js";
import { FileText, ArrowRight } from "lucide-vue-next";
const props = defineProps({ teacher: Boolean, tasks: Array });
const store = useLearning();
const visibleTasks = computed(() => props.tasks || store.data.tasks || []);
function status(task) {
  return props.teacher
    ? task.summary?.status || "待开始"
    : task.status ||
        (store.data.records[task.id]?.completed ? "已提交" : "待开始");
}
async function open(task, teacher) {
  if (!(await store.save())) return;
  await store.load(store.data.lesson?.id, true);
  store.selectTask(task.id);
  navigate(`${teacher ? "insights" : "learn"}?task=${task.id}`);
}
</script>
<template>
  <div v-if="visibleTasks.length">
    <div v-for="task in visibleTasks" :key="task.id" class="task-row">
      <span class="task-icon blue"><FileText :size="20" /></span>
      <div class="task-description">
        <h3>{{ task.title }}</h3>
        <p>
          {{ task.className || store.data.classroom?.name || "班级" }} ·
          {{ deadlineText(task.dueAt) }}
        </p>
      </div>
      <div class="task-progress-summary">
        <span v-if="teacher && task.summary"
          >{{ task.summary.submitted }}/{{ task.summary.assigned }} 已提交</span
        ><span v-if="teacher && task.summary?.overdue"
          >{{ task.summary.overdue }} 人逾期</span
        ><Status
          :tone="
            ['已提交', '全员已提交', '已反馈', '已完成反馈'].includes(
              status(task),
            )
              ? 'green'
              : status(task).includes('逾期')
                ? 'amber'
                : 'neutral'
          "
          >{{ status(task) }}</Status
        >
      </div>
      <Button variant="ghost" @click="open(task, teacher)"
        >{{ teacher ? "查看学情" : "进入任务" }}<ArrowRight
      /></Button>
    </div>
  </div>
  <div v-else class="empty-state">
    <h3>{{ teacher ? "当前班级暂无任务" : "暂无已分配任务" }}</h3>
    <RouteButton v-if="teacher" route="prepare">开始备课</RouteButton>
  </div>
</template>
