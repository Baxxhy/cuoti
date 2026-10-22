<template>
  <view class="question-content">
    <template v-for="(block, index) in blocks" :key="index">
      <math-text
        v-if="block.kind === 'text'"
        :text="block.text"
        :inline="inline"
        :subject="subject"
      />
      <view v-else-if="block.kind === 'missing'" class="image-status" role="alert">
        {{ imageLabel }}缺失，请核对题目
      </view>
      <view v-else-if="failed[block.url]" class="image-status" role="alert">
        <text>{{ imageLabel }}暂时无法加载</text>
        <button class="retry-image" role="button" @click.stop="retry(block.url)">重新加载</button>
      </view>
      <image
        v-else
        :key="`${block.url}:${revision}`"
        class="content-image"
        :class="{ 'can-preview': previewable }"
        :src="mediaUrl(block.url)"
        mode="widthFix"
        :alt="`${imageLabel}${block.index + 1}`"
        :role="previewable ? 'button' : undefined"
        :tabindex="previewable ? 0 : undefined"
        :aria-label="previewable ? `放大${imageLabel}${block.index + 1}` : undefined"
        @error="failed[block.url] = true"
        @click="preview(block.url, $event)"
        @keydown.enter.prevent="preview(block.url)"
      />
    </template>
  </view>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import MathText from '@/components/math-text/math-text.vue'
import { mediaUrl } from '@/api/index.js'
import { questionContentBlocks } from '@/utils/question-content'
const props = withDefaults(
  defineProps<{
    text?: string | null
    images?: string[]
    imageLabel?: string
    inline?: boolean
    subject?: string
    previewable?: boolean
  }>(),
  { text: '', images: () => [], imageLabel: '题图', inline: true, previewable: true, subject: '' },
)
const blocks = computed(() => questionContentBlocks(props.text || '', props.images))
const failed = ref<Record<string, boolean>>({}),
  revision = ref(0)
function retry(url: string) {
  failed.value[url] = false
  revision.value++
}
function preview(url: string, event?: Event) {
  if (!props.previewable) return
  event?.stopPropagation()
  uni.previewImage({ current: mediaUrl(url), urls: props.images.map((image) => mediaUrl(image)) })
}
watch(
  () => [props.text, props.images],
  () => {
    failed.value = {}
  },
)
</script>
<style scoped>
.question-content {
  min-width: 0;
  width: 100%;
}
.content-image {
  display: block;
  width: 100%;
  max-width: 600px;
  margin: 12px auto;
}
.content-image.can-preview {
  cursor: zoom-in;
}
.image-status {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  padding: 12px;
  margin: 12px 0;
  font-size: 14px;
  line-height: 1.6;
  color: var(--color-text-secondary);
  background: var(--color-surface-subtle);
  border-radius: 8px;
}
.retry-image {
  min-height: 44px;
  margin: 0;
  padding: 8px 12px;
  background: var(--color-surface);
  color: var(--color-primary);
  font-size: 14px;
}
</style>
