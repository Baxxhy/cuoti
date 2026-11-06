<template>
  <!-- 普通文本已在 renderMathText 中转义，仅 KaTeX 生成受控 HTML。 -->
  <view class="math-text">
    <view class="math-content" v-html="html" />
    <text v-if="needsReview" class="math-notice" role="status">公式原文待核对</text>
  </view>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { renderMathText } from '@/utils/math'

const props = withDefaults(
  defineProps<{
    text?: string | null
    inline?: boolean
    subject?: string
  }>(),
  {
    text: '',
    inline: false,
    subject: '',
  },
)

const html = computed(() => renderMathText(props.text, props.inline, props.subject))
const needsReview = computed(() => html.value.includes('class="math-unparsed"'))
</script>

<style scoped lang="scss">
.math-text {
  display: block;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  line-height: 1.8;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  overflow-x: auto;
  overflow-y: hidden;
  -webkit-overflow-scrolling: touch;
}

.math-notice {
  display: block;
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.5;
  color: #925014;
}

.math-text:deep(.math-unparsed) {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.math-text:deep(.katex-display) {
  margin: 0.6em 0;
  overflow-x: auto;
  overflow-y: hidden;
}

.math-text:deep(.katex) {
  white-space: normal;
}

.math-text:deep(.katex-display .katex) {
  white-space: nowrap;
}

.math-text:deep(.math-table) {
  display: block;
  max-width: 100%;
  overflow-x: auto;
  overflow-y: hidden;
}

.math-text:deep(.question-table) {
  border-collapse: collapse;
  white-space: normal;
  margin: 8px 0;
  font-size: inherit;
}

.math-text:deep(.question-table th),
.math-text:deep(.question-table td) {
  border: 1px solid #dce0e8;
  padding: 6px 8px;
  text-align: center;
  min-width: 28px;
}

.math-text:deep(.question-table th) {
  background: #f5f7fa;
  font-weight: 500;
}

.math-text:deep(.math-table::-webkit-scrollbar) {
  height: 5px;
}

.math-text:deep(.math-table::-webkit-scrollbar-thumb) {
  background: #c7cad1;
  border-radius: 4px;
}
</style>
