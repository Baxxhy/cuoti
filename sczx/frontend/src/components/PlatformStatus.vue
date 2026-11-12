<script setup>
import { useLearning } from "@/store.js";
const store = useLearning();
</script>
<template>
  <div v-if="store.status === 'loading'" class="page-content" role="status">
    <Surface><AppEmpty class="empty-state">正在读取学习记录…</AppEmpty></Surface>
  </div>
  <div v-else-if="store.status === 'error'" class="page-content">
    <Surface
      ><AppEmpty class="empty-state"><h2>记录读取失败</h2><p role="alert">{{ store.error }}</p><AppButton @click="store.load">重新读取</AppButton
        ><RouteButton route="issues" secondary>导出或重置演示</RouteButton></AppEmpty></Surface
    >
  </div>
</template>
