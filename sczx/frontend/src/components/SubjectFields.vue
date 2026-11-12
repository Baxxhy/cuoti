<script setup>
import{computed}from'vue';import{ElSelect,ElOption}from'element-plus';import{useEducation}from'@/services/education.js';
const grade=defineModel('grade'),subject=defineModel('subject');defineProps({disabled:Boolean});const{catalog}=useEducation();const grades=computed(()=>catalog.value.stages.flatMap(s=>s.grades||[]));
</script>
<template><div class="subject-fields"><label class="field-label">年级<ElSelect v-model="grade" aria-label="年级" :disabled="disabled" filterable allow-create default-first-option placeholder="选择年级"><ElOption v-for="value in grades" :key="value" :value="value" :label="value"/></ElSelect></label><label class="field-label">学科<ElSelect v-model="subject" aria-label="学科" :disabled="disabled" filterable allow-create default-first-option placeholder="选择或输入学科"><ElOption v-for="item in catalog.subjects" :key="item.value" :value="item.value" :label="item.label"/></ElSelect></label></div></template>
