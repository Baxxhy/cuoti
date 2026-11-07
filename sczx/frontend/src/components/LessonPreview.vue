<script setup>
import { BookOpen } from "lucide-vue-next";
import { useLearning } from "@/store.js";
const store = useLearning();
</script>
<template>
  <div class="student-preview">
    <div class="preview-top">
      <span class="preview-avatar"><BookOpen :size="17" /></span
      ><span>学生会看到的内容</span><Status>预览</Status>
    </div>
    <div class="preview-course-cover">
      <img src="/images/equation-balance.png" alt="学生课时封面" />
      <div>
        <span>第一课</span>
        <h3>等式性质</h3>
      </div>
    </div>
    <div class="preview-lesson-body">
      <span class="tiny-label">学习目标</span>
      <p class="preview-goal">{{ store.lessonGoal }}</p>
      <div
        v-for="(block, index) in store.blocks"
        :key="block.id"
        class="preview-activity"
      >
        <span>{{ index + 1 }}</span>
        <div>
          <h4>{{ block.title }}</h4>
          <p>{{ block.content }}</p>
        </div>
      </div>
      <div class="article-equation">a = b ⇒ a + c = b + c</div>
    </div>
  </div>
</template>
