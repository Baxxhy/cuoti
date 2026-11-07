<script setup>
import { useLearning } from "@/store.js";
const store = useLearning();
</script>
<template>
  <div v-if="store.status === 'loading'" class="page-content" role="status">
    <Surface><div class="empty-state">正在读取学习记录…</div></Surface>
  </div>
  <div v-else-if="store.status === 'error'" class="page-content">
    <Surface
      ><div class="empty-state">
        <h2>记录读取失败</h2>
        <p role="alert">{{ store.error }}</p>
        <Button @click="store.load">重新读取</Button
        ><RouteButton route="issues" secondary>导出或重置演示</RouteButton>
      </div></Surface
    >
  </div>
</template>
