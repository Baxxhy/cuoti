<script setup>
import{ElTabs,ElTabPane}from'element-plus';defineProps({items:{default:()=>[]}});const model=defineModel();
</script>
<template><ElTabs v-model="model" class="app-element-tabs" data-slot="tabs"><ElTabPane v-for="item in items" :key="item.value" :name="item.value" :label="item.label" :disabled="item.disabled"/></ElTabs></template>
