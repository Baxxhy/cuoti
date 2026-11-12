<script setup>
import { ChevronRight } from "@/components/app/icons.js";
import { navigate } from "@/lib/navigation.js";
defineProps({ route: String, secondary: Boolean });
</script>
<template>
  <AppButton :variant="secondary ? 'outline' : 'default'" @click="navigate(route)"
    ><slot /><ChevronRight data-icon="inline-end"
  /></AppButton>
</template>
