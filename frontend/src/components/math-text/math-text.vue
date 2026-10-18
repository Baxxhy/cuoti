<template>
  <!-- 普通文本已在 renderMathText 中转义，仅 KaTeX 生成受控 HTML。 -->
  <view class="math-text" v-html="html" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { renderMathText } from '@/utils/math'

const props = withDefaults(
  defineProps<{
    text?: string | null
    inline?: boolean
  }>(),
  {
    text: '',
    inline: false,
  },
)

const html = computed(() => renderMathText(props.text, props.inline))
</script>

<style scoped lang="scss">
.math-text {
  display: block;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  overflow-x: auto;
  overflow-y: hidden;
  -webkit-overflow-scrolling: touch;
}

.math-text:deep(.katex-display) {
  margin: 0.6em 0;
  overflow-x: auto;
  overflow-y: hidden;
}

.math-text:deep(.katex) {
  white-space: nowrap;
}
</style>
