<script setup>
import { ChevronRight } from "lucide-vue-next";
import { navigate } from "@/lib/navigation.js";
defineProps({ title: String, action: String, route: String });
</script>
<template>
  <div class="section-heading">
    <h2>{{ title }}</h2>
    <AppButton v-if="action" variant="ghost" size="sm" @click="navigate(route)"
      >{{ action }}<ChevronRight /></AppButton
    ><slot />
  </div>
</template>
