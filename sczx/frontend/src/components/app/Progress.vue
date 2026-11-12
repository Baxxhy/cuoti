<script setup>import{computed}from'vue';import{ElProgress}from'element-plus';const props=defineProps({modelValue:{default:0},max:{default:100}});const percentage=computed(()=>Math.max(0,Math.min(100,Number(props.modelValue||0)/Number(props.max||100)*100)));</script>
<template><ElProgress :percentage="percentage" :show-text="false" :stroke-width="6" data-slot="progress"/></template>
