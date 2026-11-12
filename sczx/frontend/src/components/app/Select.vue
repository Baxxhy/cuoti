<script setup>
import{ElSelect,ElOption}from'element-plus';
defineOptions({inheritAttrs:false});defineProps({options:{default:()=>[]},label:String,placeholder:String});const model=defineModel();
</script>
<template><ElSelect v-model="model" v-bind="$attrs" :aria-label="label" :placeholder="placeholder||label" data-slot="select-trigger" class="app-element-select"><ElOption v-for="option in options" :key="option.value" :value="option.value" :label="option.label" :disabled="option.disabled"/></ElSelect></template>
