<script setup>
import { useRoute } from "vue-router";
import { navigate } from "@/lib/navigation.js";
import { ArrowLeft, History } from "lucide-vue-next";
const route = useRoute();
function backToMemory() {
  const params = new URLSearchParams();
  if (route.query.returnKnowledge)
    params.set("knowledge", String(route.query.returnKnowledge));
  if (route.query.returnTask)
    params.set("returnTask", String(route.query.returnTask));
  navigate("memory" + (params.size ? "?" + params.toString() : ""));
}
</script>
<template>
  <div
    v-if="route.query.returnTask || route.query.returnKnowledge"
    class="memory-return"
  >
    <AppButton
      v-if="route.query.returnTask"
      variant="outline"
      @click="navigate('learn?task=' + route.query.returnTask)"
      ><ArrowLeft />返回当前课时</AppButton
    ><AppButton variant="ghost" @click="backToMemory"
      ><History />查看复习记录</AppButton
    >
  </div>
</template>
