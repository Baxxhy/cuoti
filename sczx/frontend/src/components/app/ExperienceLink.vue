<script setup>
import { BookOpen, ChevronRight } from "lucide-vue-next";
import { navigate } from "@/lib/navigation.js";
</script>
<template>
  <Button
    variant="ghost"
    class="experience-link"
    @click="navigate('case-detail')"
    ><BookOpen :size="15" />参考案例<ChevronRight :size="14"
  /></Button>
</template>
