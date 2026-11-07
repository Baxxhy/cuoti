<script setup>
import { useLearning } from "@/store.js";
import { questions } from "@/data.js";
const store = useLearning();
</script>
<template>
  <PageHeading title="学习记录" /><Surface
    v-for="task in store.data.tasks"
    :key="task.id"
    class="records-surface"
    ><SectionHeading :title="task.title" />
    <p class="muted">
      {{ new Date(task.publishedAt).toLocaleString("zh-CN") }}
    </p>
    <div
      v-for="attempt in store.data.records[task.id].attempts"
      :key="attempt.id"
      class="record-row"
    >
      <div>
        <h3>
          {{ (task.questions || questions)[attempt.question]?.equation }} →
          {{ attempt.answer }}
        </h3>
        <p>{{ attempt.reason || "未填写解释" }}</p>
        <small>{{ new Date(attempt.createdAt).toLocaleString("zh-CN") }}</small>
      </div>
      <Status :tone="attempt.correct ? 'green' : 'amber'">{{
        attempt.correct ? "数值正确" : "需订正"
      }}</Status
      ><Status>{{ attempt.helped ? "获得帮助" : "独立作答" }}</Status>
    </div>
    <div
      v-if="!store.data.records[task.id].attempts.length"
      class="empty-state"
    >
      还没有检查记录
    </div></Surface
  ><Surface v-if="!store.data.tasks.length"
    ><div class="empty-state">
      <h3>暂无学习记录</h3>
      <RouteButton route="home">查看学习任务</RouteButton>
    </div></Surface
  >
</template>
