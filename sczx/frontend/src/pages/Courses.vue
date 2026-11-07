<script setup>
import { useLearning } from "@/store.js";
const store = useLearning();
</script>
<template>
  <PageHeading title="课程" />
  <div class="course-collection">
    <div class="course-cover">
      <img src="/images/equation-balance.png" alt="一元一次方程课程封面" />
    </div>
    <div class="course-overview">
      <Status tone="blue">七年级数学</Status>
      <h2>一元一次方程</h2>
      <RouteButton :route="store.task ? 'learn' : 'home'">{{
        store.task ? "进入等式性质" : "查看学习任务"
      }}</RouteButton>
    </div>
  </div>
  <SectionHeading title="单元课时" /><Surface
    ><div class="lesson-row">
      <span class="lesson-number">1</span>
      <div><h3>等式性质</h3></div>
      <Status :tone="store.task ? 'green' : 'neutral'">{{
        store.task ? "已开放" : "等待发布"
      }}</Status
      ><RouteButton v-if="store.task" route="learn" secondary
        >进入课时</RouteButton
      >
    </div>
    <div
      v-for="(name, index) in ['解简单的一元一次方程', '用方程解决生活问题']"
      :key="name"
      class="lesson-row"
    >
      <span class="lesson-number">{{ index + 2 }}</span>
      <h3>{{ name }}</h3>
      <Status>待开放</Status>
    </div></Surface
  >
</template>
