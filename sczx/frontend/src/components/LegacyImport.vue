<script setup>
import { computed, ref } from "vue";
import AppDialog from "@/components/app/Dialog.vue";
import { readLegacyData } from "@/services/api.js";
import { useLearning } from "@/store.js";
const store = useLearning();
const legacy = ref(readLegacyData());
const open = ref(false);
const busy = ref(false);
const error = ref(legacy.value?.error || "");
const result = ref("");
const rawData = computed(() => legacy.value?.data?.state || legacy.value?.data || {});
const oldRecord = computed(() => Object.values(rawData.value.records || {})[0] || rawData.value);
const counts = computed(() => ({
  tasks: rawData.value.tasks?.length || (rawData.value.published || oldRecord.value.attempts?.length ? 1 : 0),
  attempts: oldRecord.value.attempts?.length || 0,
  helps: oldRecord.value.helps?.length || 0,
  wrong: oldRecord.value.wrongQuestions?.length || (oldRecord.value.wrongQuestion ? 1 : 0),
  repairs: oldRecord.value.repairs?.length || 0,
}));
async function importNow() {
  if (!legacy.value?.data || busy.value) return;
  busy.value = true;
  error.value = "";
  try {
    const response = await store.importLegacy({ sourceId: legacy.value.sourceId, data: legacy.value.data, confirmed: true });
    result.value = response.imported ? "历史演示记录已导入。原浏览器记录仍保留。" : "这份记录之前已经导入。";
    open.value = false;
    legacy.value = null;
    await store.load();
  } catch (problem) { error.value = problem.message; }
  finally { busy.value = false; }
}
</script>

<template>
  <section class="legacy-import">

    <p v-if="result" role="status">{{ result }}</p>
    <p v-else-if="legacy?.data">找到一份旧记录。</p>
    <p v-else-if="!legacy">没有可导入的旧记录。</p>
    <p v-if="error" class="form-error" role="alert">{{ error }}</p>
    <Button v-if="legacy?.data" variant="outline" @click="open = true">预览并导入</Button>
    <AppDialog v-model:open="open" title="导入历史演示记录">
      <div class="legacy-counts"><div v-for="(count, label) in { 学习任务: counts.tasks, 作答: counts.attempts, 求助: counts.helps, 错题: counts.wrong, 补救: counts.repairs }" :key="label"><strong>{{ count }}</strong><span>{{ label }}</span></div></div>
      <p>记录将归入独立的历史演示班级和学生，不计入真实学生学情。导入不会删除原浏览器数据。</p>
      <p v-if="error" class="form-error" role="alert">{{ error }}</p>
      <div class="paper-actions"><Button variant="outline" @click="open = false">取消</Button><Button :disabled="busy" @click="importNow">{{ busy ? "导入中…" : "确认导入" }}</Button></div>
    </AppDialog>
  </section>
</template>
