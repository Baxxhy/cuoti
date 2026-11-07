<script setup>
import { ref, inject } from "vue";
import { Users } from "lucide-vue-next";
import TaskList from "@/components/TaskList.vue";
import { useLearning } from "@/store.js";
const store = useLearning(),
  invite = ref(false),
  notify = inject("notify");
async function copy() {
  try {
    await navigator.clipboard.writeText("SCZX-7A");
    notify("演示口令已复制");
  } catch {
    notify("演示口令 SCZX-7A");
  }
}
</script>
<template>
  <PageHeading title="七年级一班"
    ><Button variant="outline" @click="invite = true"><Users />邀请学生</Button
    ><RouteButton route="prepare">发布新任务</RouteButton></PageHeading
  >
  <div class="class-banner">
    <div class="class-mark"><Users :size="35" /></div>
    <div><p>1 名可操作演示学生 · 七年级数学</p></div>
    <div class="student-avatars"><span>林</span></div>
  </div>
  <SectionHeading title="班级学习任务" /><Surface><TaskList teacher /></Surface
  ><AppDialog v-model:open="invite" title="邀请学生"
    ><div class="invitation-code">SCZX-7A</div>
    <InfoTip label="邀请范围"
      >演示口令用于展示邀请流程。真实成员加入将在后端接入后开放。</InfoTip
    ><Button @click="copy">复制口令</Button></AppDialog
  >
</template>
