<script setup>
import { ChevronRight } from "lucide-vue-next";
import { navigate } from "@/lib/navigation.js";
defineProps({ route: String, secondary: Boolean });
</script>
<template>
  <Button :variant="secondary ? 'outline' : 'default'" @click="navigate(route)"
    ><slot /><ChevronRight data-icon="inline-end"
  /></Button>
</template>
