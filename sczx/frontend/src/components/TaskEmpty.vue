<script setup>
import { navigate } from "@/lib/navigation.js";
defineProps({ title: { default: "还没有学习任务" } });
</script>
<template>
  <Surface
    ><AppEmpty class="empty-state"><h2>{{ title }}</h2><RouteButton route="class">查看班级任务</RouteButton
      ><AppButton variant="outline" @click="navigate('prepare')"
        >去备课并发布</AppButton
      ></AppEmpty></Surface
  >
</template>
