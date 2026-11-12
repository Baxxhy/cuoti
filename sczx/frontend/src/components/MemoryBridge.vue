<script setup>
import { ref, watch, onBeforeUnmount, computed } from "vue";
import { ArrowRight, History } from "@/components/app/icons.js";
import { memoryApi, memoryTarget } from "@/services/memory.js";
import { navigate } from "@/lib/navigation.js";
const props = defineProps({
  task: { type: Object, default: null },
  compact: Boolean,
});
const data = ref(null),
  error = ref("");
let generation = 0;
const ids = computed(
  () =>
    props.task?.snapshot.lessonSnapshot?.knowledgeIds ||
    props.task?.snapshot.knowledgeIds ||
    [],
);
const suggestions = computed(
  () =>
    data.value?.recommendations
      .filter((r) => !props.task || ids.value.includes(r.knowledgeId))
      .slice(0, props.compact ? 1 : 3) || [],
);
async function load() {
  const g = ++generation;
  data.value = null;
  error.value = "";
  try {
    const result = await memoryApi.overview();
    if (g === generation) data.value = result;
  } catch (e) {
    if (g === generation) error.value = e.message;
  }
}
watch(() => props.task?.id, load, { immediate: true });
onBeforeUnmount(() => generation++);
</script>
<template>
  <Surface data-ui="card" v-if="suggestions.length || error" class="memory-bridge">
    <div class="memory-bridge-heading">
      <History :size="17" />
      <h2>{{ task ? "相关复习" : "接着练习" }}</h2>
      <AppButton
        variant="ghost"
        size="sm"
        @click="navigate('memory' + (task ? '?returnTask=' + task.id : ''))"
        >查看复习<ArrowRight
      /></AppButton>
    </div>
    <AppAlert type="error" v-if="error" role="alert">
      {{ error }}<AppButton variant="ghost" @click="load">重试</AppButton>
    </AppAlert>
    <Surface data-ui="card" role="article" v-for="r in suggestions" :key="r.id">
      <div>
        <strong>{{
          data.items.find((i) => i.id === r.knowledgeId)?.name
        }}</strong>
        <p>{{ r.reason }}</p>
      </div>
      <AppButton
        variant="outline"
        size="sm"
        @click="
          navigate(memoryTarget(r.target, task?.id, r.knowledgeId).slice(1))
        "
        >{{ r.label }}<ArrowRight
      /></AppButton>
    </Surface>
  </Surface>
</template>
