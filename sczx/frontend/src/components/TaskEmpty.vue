<script setup>
import { navigate } from "@/lib/navigation.js";
defineProps({ title: { default: "还没有学习任务" } });
</script>
<template>
  <Surface
    ><div class="empty-state">
      <h2>{{ title }}</h2>
      <RouteButton route="class">查看班级任务</RouteButton
      ><Button variant="outline" @click="navigate('prepare')"
        >去备课并发布</Button
      >
    </div></Surface
  >
</template>
