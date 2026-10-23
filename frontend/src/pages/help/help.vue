<template>
  <view class="page">
    <app-header title="使用指南" back />
    <view class="page-content">
      <view v-for="section in sections" :key="section.title" class="help-section">
        <h2>{{ section.title }}</h2>
        <text>{{ section.content }}</text>
        <button role="button" v-if="section.url" class="secondary-btn" @click="go(section.url)">
          {{ section.action }}
        </button>
      </view>
    </view>
  </view>
</template>
<script setup>
import { go } from '@/utils/navigation.js'
const sections = [
  {
    title: '刚做错一道题',
    content:
      '录入时拍清题目、选项和自己的过程。先核对识别结果，再找错因；没有作答也可以先保存题目。',
    action: '录入错题',
    url: '/pages/capture/capture',
  },
  {
    title: '解析和诊断有什么不同',
    content:
      '解析说明题目怎么做；诊断根据你的答案和步骤寻找问题。若错因不符合实际，在诊断页修正；若题目识别错了，先修改录入内容。',
  },
  {
    title: '练习和复习怎么选',
    content:
      '针对练习围绕一道错题匹配题库；复习按已有学习记录安排到期任务，先独立作答再看反馈。暂时没有任务时，可以主动挑题学习。',
    action: '进入学习中心',
    url: '/pages/learning/learning',
  },
  {
    title: '怎样判断是否学会',
    content:
      '看完解析后，试着不看提示重新做一遍，再通过类似题和后续复习巩固。学习记录会保留作答结果；判题待核对时，先确认答案再继续。',
  },
  {
    title: '考前集中整理',
    content:
      '在错题中按学科、知识点、错因或收藏找到目标题，再按当前条件组卷。空白题和答案解析分别导出，纸上练完后仍需要检查过程。',
    action: '查看错题',
    url: '/pages/problem/list',
  },
  {
    title: '报告与知识图谱',
    content:
      '报告帮助发现需要关注的地方；图谱展示相关知识和错题。分数是学习记录的估计，不是考试分数，也不能证明所有相关题都会做。',
  },
  {
    title: '遇到问题怎么办',
    content:
      '加载失败可重试；提交失败时先保留当前作答再重试。题目和原作答修改后，请按修改后的题目重新作答。',
  },
]
</script>
<style scoped lang="scss">
.help-section {
  padding: 8px 0 20px;
  border-bottom: 1px solid var(--color-border);
  margin-bottom: 12px;
}
h2 {
  font-size: 18px;
  margin: 12px 0;
}
.help-section text {
  display: block;
  font-size: 16px;
  line-height: 1.8;
}
</style>
