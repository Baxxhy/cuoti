<script setup>
import { ref, inject } from "vue";
import { useLearning } from "@/store.js";
import { simulateNextFailure, storageKey } from "@/services/platform.js";
const store = useLearning(),
  notify = inject("notify"),
  modal = ref(false),
  resetOpen = ref(false),
  reply = ref(store.data.issue.reply),
  busy = ref(false),
  error = ref("");

async function retry() {
  if (busy.value) return;
  busy.value = true;
  error.value = "";
  store.data.runtime.status = "running";
  store.touch();
  if (await store.save()) {
    store.data.runtime.status = "completed";
    store.data.runtime.updatedAt = new Date().toISOString();
    store.touch();

    notify("演示任务重试完成");
  } else {
    store.data.runtime.status = "failed";
    error.value = store.saveError;
  }
  busy.value = false;
}
function resolve() {
  if (!reply.value.trim()) return notify("请填写回复");
  store.data.issue.reply = reply.value;
  store.data.issue.resolved = true;
  store.data.issue.updatedAt = new Date().toISOString();
  store.touch();
  modal.value = false;
  notify("反馈回复已记录");
}
function download() {
  const payload = {
    current: store.data,
    stored: localStorage.getItem(storageKey),
    legacyVue: localStorage.getItem("shicheng-vue-prototype"),
    legacyReact: localStorage.getItem("shicheng-nova-prototype-v2"),
  };
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = "师承智学演示记录.json";
  link.click();
  URL.revokeObjectURL(url);
}
async function reset() {
  busy.value = true;
  error.value = "";
  try {
    await store.reset();
    resetOpen.value = false;
    notify("演示已重置");
  } catch (problem) {
    error.value = problem.message;
  } finally {
    busy.value = false;
  }
}
</script>
<template>
  <PageHeading title="反馈与运行" />
  <p v-if="error" class="form-error" role="alert">{{ error }}</p>
  <Surface
    ><SectionHeading title="内容反馈" />
    <div class="feedback-issue">
      <div>
        <h3>{{ store.data.issue.text }}</h3>
        <p>等式性质 · 观察活动</p>
      </div>
      <Status :tone="store.data.issue.resolved ? 'green' : 'amber'">{{
        store.data.issue.resolved ? "已处理" : "待处理"
      }}</Status
      ><Button variant="outline" @click="modal = true">{{
        store.data.issue.resolved ? "查看回复" : "处理反馈"
      }}</Button>
    </div></Surface
  ><Surface class="runtime-surface"
    ><SectionHeading title="任务运行" />
    <div class="feedback-issue">
      <div>
        <h3>配套教学内容生成</h3>
        <p>本地演示任务</p>
      </div>
      <Status
        :tone="store.data.runtime.status === 'completed' ? 'green' : 'amber'"
        >{{
          store.data.runtime.status === "completed"
            ? "重试成功"
            : busy
              ? "重试中"
              : "模拟失败"
        }}</Status
      ><Button
        variant="outline"
        :disabled="busy || store.data.runtime.status === 'completed'"
        @click="retry"
        >重试任务</Button
      >
    </div></Surface
  ><Surface class="runtime-surface"
    ><SectionHeading title="演示数据" />
    <div class="paper-actions">
      <Button variant="outline" @click="download">导出记录</Button
      ><Button variant="outline" @click="resetOpen = true">重置演示</Button>
    </div>
    <details class="developer-options">
      <summary>演示调试</summary>
      <p>触发指定操作失败，检查错误提示与重试。</p>
      <Button
        variant="outline"
        @click="
          simulateNextFailure('publish');
          notify('下一次发布将模拟失败');
        "
        >模拟下次发布失败</Button
      >
      <Button
        variant="outline"
        @click="
          simulateNextFailure('save');
          notify('下一次保存将模拟失败');
        "
        >模拟下次保存失败</Button
      >
    </details></Surface
  ><AppDialog v-model:open="modal" title="回复学习疑问"
    ><Textarea v-model="reply" aria-label="反馈回复" /><Button @click="resolve"
      >确认处理</Button
    ></AppDialog
  ><AppDialog v-model:open="resetOpen" title="重置演示记录"
    ><p>
      将清除当前演示的教案修改、发布任务、作答、题图和反馈，恢复初始内容。建议先导出记录。
    </p>
    <div class="paper-actions">
      <Button variant="outline" @click="resetOpen = false">取消</Button
      ><Button :disabled="busy" @click="reset">确认重置</Button>
    </div></AppDialog
  >
</template>
