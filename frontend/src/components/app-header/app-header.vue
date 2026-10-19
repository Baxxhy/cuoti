<template>
  <view class="app-header">
    <view
      v-if="back"
      class="header-action"
      role="button"
      tabindex="0"
      aria-label="返回"
      @tap.stop="handleBack"
      @keydown.enter="handleBack"
    >
      <uni-icons aria-hidden="true" type="left" size="24" color="var(--color-text-primary)" />
    </view>
    <view class="header-copy">
      <!-- #ifdef H5 -->
      <component :is="'h1'" class="header-title">
        <math-text v-if="hasMath" :text="title" inline />
        <template v-else>{{ title }}</template>
      </component>
      <!-- #endif -->
      <!-- #ifndef H5 -->
      <view v-if="hasMath" class="header-title"><math-text :text="title" inline /></view>
      <text v-else class="header-title">{{ title }}</text>
      <!-- #endif -->
    </view>
    <view v-if="$slots.default" class="header-extra"><slot /></view>
  </view>
</template>
<script setup>
import { computed } from 'vue'
import MathText from '@/components/math-text/math-text.vue'
import { back as goBack } from '@/utils/navigation.js'
const props = defineProps({
  title: { type: String, required: true },
  back: Boolean,
  gradient: Boolean,
  backFallback: String,
})
const hasMath = computed(() => /[$\\]/.test(props.title))
function handleBack() {
  goBack(props.backFallback)
}
</script>
<style scoped lang="scss">
.app-header {
  min-height: calc(64px + var(--status-bar-height, 0px));
  padding: calc(10px + var(--status-bar-height, 0px)) var(--space-page) 10px;
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--color-bg);
  position: relative;
  z-index: 10;
}
.header-copy {
  flex: 1;
  min-width: 0;
}
.header-title {
  display: block;
  margin: 0;
  font-size: 21px;
  font-weight: 600;
  line-height: 1.25;
  letter-spacing: -0.035em;
}
.header-action {
  flex: none;
  width: 44px;
  min-height: 44px;
  margin-left: -10px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  cursor: pointer;
}
.header-action:active {
  background: var(--color-surface-subtle);
}
.header-extra {
  display: flex;
  align-items: center;
  min-height: 44px;
  flex-shrink: 0;
}
@media (min-width: 1100px) {
  .app-header {
    padding-top: 28px;
    padding-bottom: 8px;
  }
}
</style>
