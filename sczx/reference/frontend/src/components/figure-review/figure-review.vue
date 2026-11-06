<template>
  <view v-if="rows.length" class="figure-review">
    <button
      class="figure-toggle"
      role="button"
      tabindex="0"
      :aria-label="opened ? '收起图形标注' : `查看图形标注 · ${rows.length}`"
      :aria-expanded="opened"
      @click="opened = !opened"
      @keydown.enter.prevent="opened = !opened"
      @keydown.space.prevent
      @keyup.space.prevent="opened = !opened"
    >
      <uni-icons aria-hidden="true" type="images" size="18" color="var(--color-primary)" />
      <text class="figure-toggle-label">
        {{ opened ? '收起图形标注' : `查看图形标注 · ${rows.length}` }}
      </text>
      <uni-icons
        aria-hidden="true"
        :type="opened ? 'top' : 'bottom'"
        size="16"
        color="var(--color-text-secondary)"
      />
    </button>
    <view v-if="opened" class="figure-body">
      <text class="figure-intro">
        只核对你的图，原题条件以题干为准。这次使用了图形提示，会按辅助学习记录。
      </text>
      <view v-for="(row, index) in rows" :key="index" class="figure-row">
        <view class="figure-head">
          <math-text class="figure-label" :text="row.label" inline />
          <text class="figure-status" :class="row.status">
            {{ labels[row.status] || '待核对' }}
          </text>
        </view>
        <math-text class="figure-message" :text="row.message" inline />
        <view v-if="showBasis" class="figure-basis">
          <text>照片转写</text>
          <math-text :text="row.evidence_quote" inline />
          <template v-if="row.source_quote">
            <text>原题条件</text>
            <math-text :text="row.source_quote" inline />
          </template>
        </view>
      </view>
      <button
        class="basis-toggle"
        role="button"
        tabindex="0"
        :aria-expanded="showBasis"
        @click="showBasis = !showBasis"
        @keydown.enter.prevent="showBasis = !showBasis"
        @keydown.space.prevent
        @keyup.space.prevent="showBasis = !showBasis"
      >
        {{ showBasis ? '收起核对依据' : '查看核对依据' }}
      </button>
    </view>
  </view>
</template>
<script setup>
import { ref, watch } from 'vue'
import MathText from '@/components/math-text/math-text.vue'
const props = defineProps({ rows: { type: Array, default: () => [] } })
const opened = ref(false),
  showBasis = ref(false)
const labels = {
  matches_given: '与条件相符',
  consistent_derived: '关系一致',
  conflicts: '需要检查',
  unconfirmed: '待核对',
}
watch(
  () => props.rows,
  () => {
    opened.value = false
    showBasis.value = false
  },
)
</script>
<style scoped lang="scss">
.figure-review {
  margin-top: 12px;
  border-top: 1px solid var(--color-border);
}
.figure-toggle {
  width: 100%;
  min-height: 48px;
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0;
  padding: 12px 0;
  background: transparent;
  color: var(--color-primary);
  text-align: left;
  font-size: 14px;
  line-height: 1.5;
}
.figure-toggle::after,
.basis-toggle::after {
  border: 0;
}
.figure-toggle-label {
  flex: 1;
  min-width: 0;
  white-space: nowrap;
  text-align: left;
}
.figure-intro {
  display: block;
  margin: 4px 0 16px;
  color: var(--color-text-secondary);
  font-size: 13px;
  line-height: 1.6;
}
.figure-row {
  padding: 14px 0;
  border-bottom: 1px solid var(--color-border);
}
.figure-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.figure-label {
  flex: 1;
  min-width: 0;
  font-size: 16px;
}
.figure-status {
  flex: none;
  padding: 4px 8px;
  border-radius: 6px;
  background: var(--color-bg);
  color: var(--color-text-secondary);
  font-size: 12px;
}
.figure-status.matches_given,
.figure-status.consistent_derived {
  color: var(--color-primary);
  background: var(--color-primary-soft);
}
.figure-status.conflicts {
  color: var(--color-error);
}
.figure-message {
  display: block;
  margin-top: 8px;
  font-size: 14px;
  line-height: 1.65;
  color: var(--color-text-secondary);
}
.figure-basis {
  margin-top: 12px;
  padding: 12px;
  border-radius: 8px;
  background: var(--color-bg);
  font-size: 14px;
  line-height: 1.6;
}
.figure-basis > text {
  display: block;
  margin: 6px 0;
  color: var(--color-text-secondary);
  font-size: 12px;
}
.basis-toggle {
  min-height: 44px;
  padding: 12px 0;
  margin: 0;
  text-align: left;
  color: var(--color-primary);
  background: transparent;
  font-size: 14px;
  line-height: 1.5;
}
</style>
