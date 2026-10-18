<template>
  <view class="teaching-content">
    <template v-for="(block, index) in blocks" :key="index">
      <view v-if="allowed.includes(block.kind)" :class="['content-block', block.kind]">
        <button
          v-if="foldable(block)"
          class="expand-action"
          role="button"
          tabindex="0"
          :aria-expanded="expanded.includes(index)"
          @click="toggle(index)"
          @keydown.enter.prevent="toggle(index)"
        >
          {{ expanded.includes(index) ? '收起这段说明' : '展开这段说明' }}
        </button>
        <math-text v-if="!foldable(block) || expanded.includes(index)" :text="block.text" />
      </view>
    </template>
  </view>
</template>
<script setup>
import { ref, watch } from 'vue'
import MathText from '@/components/math-text/math-text.vue'
const props = defineProps({ blocks: { type: Array, default: () => [] } })
const allowed = ['text', 'formula', 'question']
const expanded = ref([])
const foldable = (block) => block.kind !== 'question' && String(block.text || '').length > 160
function toggle(index) {
  expanded.value = expanded.value.includes(index)
    ? expanded.value.filter((i) => i !== index)
    : [...expanded.value, index]
}
watch(
  () => props.blocks,
  () => {
    expanded.value = []
  },
)
</script>
<style scoped lang="scss">
.content-block {
  margin: 12px 0;
  font-size: 16px;
}
.content-block.question {
  font-size: 18px;
}
.content-block.formula {
  padding: 20px 12px;
  background: var(--color-primary-soft);
  border-radius: 12px;
  font-size: 22px;
}
.expand-action {
  width: 100%;
  min-height: 48px;
  padding: 12px 0;
  margin: 0;
  text-align: left;
  background: transparent;
  font-size: 14px;
  color: var(--color-primary);
}
</style>
