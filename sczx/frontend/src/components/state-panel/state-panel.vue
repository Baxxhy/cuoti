<template>
  <div class="state-panel">
    <WebLoadMore
      v-if="state === 'loading'"
      status="loading"
      :content-text="{ contentrefresh: '正在加载' }"
    />
    <template v-else>
      <WebIcon aria-hidden="true" type="info-filled" size="28" color="#94a3b8" />
      <span>{{ message || '暂时无法加载' }}</span>
      <button role="button" class="ghost-btn" @click="$emit('retry')">{{ retryText }}</button>
    </template>
  </div>
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
  min-height: 160.0px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10.0px;
  color: var(--color-text-secondary);
}
.ghost-btn {
  margin: 0;
  background: var(--color-primary-soft);
  color: var(--color-primary);
  border: 0;
  font-size: 13.0px;
}
</style>
