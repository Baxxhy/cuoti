<script setup>
import { useLearning } from "@/store.js";
const store = useLearning();
</script>
<template>
  <div v-if="store.status === 'loading'" class="page-content" role="status">
    <Surface><ElSkeleton animated :rows="4" aria-label="正在读取学习记录"/></Surface>
  </div>
  <div v-else-if="store.status === 'error'" class="page-content">
    <Surface
      ><AppEmpty class="empty-state"><h2>记录读取失败</h2><AppAlert type="error" role="alert">{{ store.error }}</AppAlert><AppButton @click="store.load">重新读取</AppButton
        ><RouteButton route="issues" secondary>导出或重置演示</RouteButton></AppEmpty></Surface
    >
  </div>
</template>
