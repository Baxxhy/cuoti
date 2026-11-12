<script setup>
import { Check, ChevronRight } from '@/components/app/icons.js';
import { readingValue } from '@/lib/lesson-reading.js';
defineProps({ lesson:Object, blocks:Array, progress:Object, selected:String });
defineEmits(['select']);
</script>
<template>
  <nav class="curriculum-outline" aria-label="本课内容">
    <button v-for="(block,i) in blocks" :key="block.id" @click="$emit('select',block.id)" :aria-current="selected===block.id?'step':undefined">
      <span>{{String(i+1).padStart(2,'0')}}</span><strong>{{readingValue(lesson,block,'title')}}</strong><Check v-if="progress[block.id]?.completed" :size="16"/><ChevronRight v-else :size="16"/>
    </button>
  </nav>
</template>
