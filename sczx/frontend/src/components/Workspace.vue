<script setup>
import { ref, onMounted, onBeforeUnmount } from "vue";
import { SplitterGroup, SplitterPanel, SplitterResizeHandle } from "reka-ui";
import { GripVertical } from "lucide-vue-next";
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
    <SplitterGroup direction="horizontal" class="workspace-panels">
      <SplitterPanel :default-size="64" :min-size="42" data-panel
        ><div class="panel-scroll"><slot name="primary" /></div
      ></SplitterPanel>
      <SplitterResizeHandle
        class="resize-handle"
        aria-label="调整主内容与参考面板宽度"
        ><GripVertical :size="13"
      /></SplitterResizeHandle>
      <SplitterPanel :default-size="36" :min-size="28" data-panel
        ><div class="panel-scroll secondary-pane"><slot name="secondary" /></div
      ></SplitterPanel>
    </SplitterGroup>
  </div>
</template>
