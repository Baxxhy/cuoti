<script setup>
import { useLearning } from "@/store.js";
import { questions } from "@/data.js";
const store = useLearning();
function exportRecords(){window.open("/api/exams/learning-records/export","_blank","noopener")}
</script>
<template>
  <PageHeading title="学习记录"><Button variant="outline" @click="exportRecords">导出记录</Button></PageHeading>
  <div v-if="store.data.tasks.length" class="student-record-list">
    <details v-for="task in store.data.tasks" :key="task.id" class="student-record-group">
      <summary><span><strong>{{task.title}}</strong><time>{{new Date(task.publishedAt).toLocaleDateString('zh-CN')}}</time></span><span>{{store.data.records[task.id]?.attempts.length||0}} 次作答</span></summary>
      <div v-for="attempt in store.data.records[task.id]?.attempts||[]" :key="attempt.id" class="record-row">
        <div><h3>{{(task.questions||questions)[attempt.question]?.equation}} → {{attempt.answer}}</h3><p>{{attempt.reason||'未填写解释'}}</p><time>{{new Date(attempt.createdAt).toLocaleString('zh-CN')}}</time></div>
        <div class="record-row-status"><Status :tone="attempt.correct?'green':'amber'">{{attempt.verification?.status==='unverified'?'需核对':attempt.correct?'数值正确':'需订正'}}</Status><Status>{{attempt.helped?'获得帮助':'独立作答'}}</Status></div>
      </div>
      <div v-if="!store.data.records[task.id]?.attempts.length" class="task-empty"><p>还没有作答</p><RouteButton :route="'learn?task='+task.id" secondary>进入学习</RouteButton></div>
      <div v-else class="action-row"><RouteButton :route="'result?task='+task.id" secondary>查看学习结果</RouteButton></div>
    </details>
  </div>
  <div v-else class="task-empty"><h2>暂无学习记录</h2><RouteButton route="home">查看学习任务</RouteButton></div>
</template>
