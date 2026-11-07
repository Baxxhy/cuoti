<script setup>
import { Button } from "@/components/ui/button/index.js";
import { motion } from "motion-v";
defineOptions({ inheritAttrs: false });
defineProps({ variant: { default: "default" }, size: { default: "default" } });
</script>
<template>
  <Button
    :as="motion.button"
    :variant="variant"
    :size="size"
    :while-hover="{ y: -1 }"
    :while-tap="{ scale: 0.98 }"
    :transition="{ duration: 0.14 }"
    v-bind="$attrs"
    ><slot
  /></Button>
</template>
