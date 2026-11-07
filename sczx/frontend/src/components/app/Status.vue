<script setup>
import { Badge } from "@/components/ui/badge/index.js";
defineProps({ tone: { default: "neutral" } });
</script>
<template>
  <Badge variant="secondary" :class="['status-badge', `tone-${tone}`]"
    ><slot
  /></Badge>
</template>
