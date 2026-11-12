<script setup>
import { ref, onMounted, onBeforeUnmount } from "vue";
import {ElSplitter,ElSplitterPanel} from "element-plus";

defineProps({primarySize:{type:Number,default:64},primaryMin:{type:Number,default:42}});
const compact = ref(window.matchMedia("(max-width: 1000px)").matches);
const query = window.matchMedia("(max-width: 1000px)");
const update = () => {
  compact.value = query.matches;
};
onMounted(() => query.addEventListener("change", update));
onBeforeUnmount(() => query.removeEventListener("change", update));
</script>
<template>
  <div v-if="compact" class="workspace-stacked">
    <div><slot name="primary" /></div>
    <div><slot name="secondary" /></div>
  </div>
  <div v-else class="workspace-frame">
    <ElSplitter class="workspace-panels">
      <ElSplitterPanel :size="primarySize+'%'" :min="primaryMin+'%'" data-panel><div class="panel-scroll"><slot name="primary"/></div></ElSplitterPanel>
      <ElSplitterPanel min="28%" data-panel><Surface data-ui="card" class="panel-scroll secondary-pane"><slot name="secondary"/></Surface></ElSplitterPanel>
    </ElSplitter>
  </div>
</template>
