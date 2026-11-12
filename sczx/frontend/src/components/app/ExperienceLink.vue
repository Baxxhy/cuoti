<script setup>
import { BookOpen, ChevronRight } from "@/components/app/icons.js";
import { navigate } from "@/lib/navigation.js";
</script>
<template>
  <AppButton
    variant="ghost"
    class="experience-link"
    @click="navigate('case-detail')"
    ><BookOpen :size="15" />参考案例<ChevronRight :size="14"
  /></AppButton>
</template>
