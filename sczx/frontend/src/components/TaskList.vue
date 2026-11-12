<script setup>
import { computed } from "vue";
import { deadlineText } from "@/services/teaching.js";
import { useLearning } from "@/store.js";
import { navigate } from "@/lib/navigation.js";
import { FileText, ArrowRight } from "@/components/app/icons.js";
const props = defineProps({ teacher: Boolean, tasks: Array, emptyLabel: String });
const store = useLearning();
const visibleTasks = computed(() => props.tasks || store.data.tasks || []);
function repeated(task){return visibleTasks.value.filter(t=>t.title===task.title&&t.classId===task.classId).length>1}
function published(task){return new Date(task.publishedAt).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:false})}
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
  const target=teacher?"insights":["exam","live-class"].includes(store.task?.source)?"records":store.task?.snapshot?.blocks?.length?"learn":"check";
  navigate(`${target}?task=${task.id}`);
}
</script>
<template>
  <div v-if="visibleTasks.length">
    <div v-for="task in visibleTasks" :key="task.id" class="task-row">
      <span class="task-icon blue"><FileText :size="20" /></span>
      <div class="task-description">
        <h3>{{ task.title }}</h3>
        <p>
          {{ task.className || store.data.classroom?.name || "班级" }}<template v-if="repeated(task)&&task.publishedAt"> 　 {{ published(task) }} 发布</template><template v-if="task.dueAt"> 　 {{ deadlineText(task.dueAt) }} 截止</template>
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
      <AppButton variant="ghost" @click="open(task, teacher)"
        >{{ teacher ? "查看学情" : "进入任务" }}<ArrowRight
      /></AppButton>
    </div>
  </div>
  <AppEmpty v-else class="empty-state"><h3>{{ emptyLabel || (teacher ? "当前班级暂无任务" : "暂无已分配任务") }}</h3><RouteButton v-if="teacher" route="prepare">开始备课</RouteButton></AppEmpty>
</template>
