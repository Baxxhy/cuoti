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
      <uni-icons type="left" size="24" color="var(--color-text-primary)" />
    </view>
    <view class="header-copy">
      <text class="header-title">{{ title }}</text>
      <text v-if="subtitle" class="header-subtitle">{{ subtitle }}</text>
    </view>
    <view v-if="$slots.default" class="header-extra"><slot /></view>
  </view>
</template>
<script setup>
import { back as goBack } from '@/utils/navigation.js'
const props = defineProps({
  title: { type: String, required: true },
  subtitle: String,
  back: Boolean,
  gradient: Boolean,
  backFallback: String,
})
function handleBack() {
  goBack(props.backFallback)
}
</script>
<style scoped lang="scss">
.app-header {
  min-height: calc(64px + var(--status-bar-height, 0px));
  padding: calc(12px + var(--status-bar-height, 0px)) var(--space-page) 12px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 10px;
  background: #fff;
  border-bottom: 1px solid var(--color-border);
  position: sticky;
  top: 0;
  z-index: 100;
}
.header-action {
  width: 48px;
  min-height: 48px;
  margin-left: -10px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  cursor: pointer;
}
.header-action:active {
  background: var(--color-bg);
}
.header-copy {
  flex: 1;
  min-width: 0;
}
.header-title,
.header-subtitle {
  display: block;
}
.header-title {
  font-size: 19px;
  font-weight: 600;
  line-height: 1.4;
}
.header-subtitle {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-top: 3px;
}
.header-extra {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 44px;
  flex-shrink: 0;
}
</style>
