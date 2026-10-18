<template>
  <view class="state-panel">
    <uni-load-more
      v-if="state === 'loading'"
      status="loading"
      :content-text="{ contentrefresh: '正在加载' }"
    />
    <template v-else>
      <uni-icons type="info-filled" size="28" color="#94a3b8" />
      <text>{{ message || '暂时无法加载' }}</text>
      <button class="ghost-btn" @click="$emit('retry')">{{ retryText }}</button>
    </template>
  </view>
</template>
<script setup>
defineProps({
  state: { type: String, default: 'loading' },
  message: String,
  retryText: { type: String, default: '重新加载' },
})
defineEmits(['retry'])
</script>
<style scoped>
.state-panel {
  min-height: 320rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 20rpx;
  color: var(--color-text-secondary);
}
.ghost-btn {
  margin: 0;
  background: var(--color-primary-soft);
  color: var(--color-primary);
  border: 0;
  font-size: 26rpx;
}
</style>
