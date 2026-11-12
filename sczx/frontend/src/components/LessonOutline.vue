<script setup>
import { Check, ChevronRight } from '@/components/app/icons.js';
import { readingValue } from '@/lib/lesson-reading.js';
defineProps({ lesson:Object, blocks:Array, progress:Object, selected:String });
defineEmits(['select']);
</script>
<template><ElMenu class="curriculum-outline" :default-active="selected" aria-label="本课内容" @select="$emit('select',$event)"><ElMenuItem v-for="(block,i) in blocks" :key="block.id" :index="block.id" :aria-current="selected===block.id?'step':undefined"><span>{{String(i+1).padStart(2,'0')}}</span><strong>{{readingValue(lesson,block,'title')}}</strong><Check v-if="progress[block.id]?.completed" :size="16"/><ChevronRight v-else :size="16"/></ElMenuItem></ElMenu></template>
