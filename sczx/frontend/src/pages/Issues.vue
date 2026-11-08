<script setup>
import { ref, inject, onMounted } from "vue";
import { useLearning } from "@/store.js";
import { api } from "@/services/api.js";
import AccountManager from "@/components/AccountManager.vue";
import LegacyImport from "@/components/LegacyImport.vue";
import ModelConsole from "@/components/ModelConsole.vue";
const store = useLearning();
const notify = inject("notify");
const reply = ref(store.data.issue?.reply || "");
const error = ref("");
const serviceStatus = ref("检查中");
async function saveReply() {
  if (!reply.value.trim()) { error.value = "请填写回复内容。"; return; }
  error.value = "";
  try {
    const result = await api.replyIssue(store.data.issue.id, reply.value.trim());
    store.data.issue.reply = result.reply;
    store.data.issue.resolved = result.resolved;
    store.data.issue.updatedAt = result.updatedAt;
    notify("回复已保存");
  } catch (problem) {
    error.value = problem.message;
  }
}
async function health() {
  try { await api.request("/health"); serviceStatus.value = "服务和数据库已连接"; }
  catch (problem) { serviceStatus.value = problem.message; }
}
onMounted(health);
</script>

<template>
  <PageHeading title="反馈与运行" />
  <p v-if="error" class="form-error" role="alert">{{ error }}</p>
  <template v-if="store.user?.role === 'admin'">
    <Surface><ModelConsole /></Surface>
    <Surface><SectionHeading title="业务服务" /><p role="status">{{ serviceStatus }}</p><Button variant="outline" @click="health">重新检查</Button></Surface>
    <Surface class="runtime-surface"><AccountManager /></Surface>
    <Surface class="runtime-surface"><LegacyImport /></Surface>
  </template>
  <Surface v-else>
    <SectionHeading title="学习疑问" />
    <div class="feedback-issue"><div><h3>{{ store.data.issue?.text || "还没有学习疑问" }}</h3><p>等式性质</p></div><Status :tone="store.data.issue?.resolved ? 'green' : 'amber'">{{ store.data.issue?.resolved ? "已回复" : "待回复" }}</Status></div>
    <label class="field-label" for="support-reply">教师回复</label>
    <Textarea id="support-reply" v-model="reply" aria-label="教师回复" />
    <Button class="save-reply" @click="saveReply">保存回复</Button>
  </Surface>
</template>
