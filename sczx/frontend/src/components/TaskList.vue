<script setup>
import { useLearning } from "@/store.js";
import { navigate } from "@/lib/navigation.js";
import { FileText, ArrowRight } from "lucide-vue-next";
defineProps({ teacher: Boolean });
const store = useLearning();
function open(task, teacher) {
  store.selectTask(task.id);
  navigate(`${teacher ? "insights" : "learn"}?task=${task.id}`);
}
</script>
<template>
  <div v-if="store.data.tasks.length">
    <div v-for="task in store.data.tasks" :key="task.id" class="task-row">
      <span class="task-icon blue"><FileText :size="20" /></span>
      <div class="task-description">
        <h3>{{ task.title }}</h3>
        <p>
          {{ store.data.classroom.name }} ·
          {{ new Date(task.publishedAt).toLocaleString("zh-CN") }}
        </p>
      </div>
      <Status
        :tone="store.data.records[task.id].completed ? 'green' : 'blue'"
        >{{
          store.data.records[task.id].completed ? "已提交" : "待完成"
        }}</Status
      ><Button variant="ghost" @click="open(task, teacher)"
        >{{ teacher ? "查看学情" : "进入任务" }}<ArrowRight
      /></Button>
    </div>
  </div>
  <div v-else class="empty-state">
    <h3>还没有发布任务</h3>
    <RouteButton v-if="teacher" route="prepare">开始备课</RouteButton>
  </div>
</template>
