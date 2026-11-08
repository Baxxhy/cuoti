<script setup>
defineProps({value:Object});
const labels={verified:'已核对',inconsistent:'不一致',unverified:'需核对'};
</script>
<template><details v-if="value?.claims?.length" class="case-math-check"><summary>数学核对</summary><p v-for="(claim,index) in value.claims" :key="index"><span>{{ claim.left }} = {{ claim.right }}</span><Status :tone="claim.status==='verified'?'green':'amber'">{{ labels[claim.status] }}</Status></p><InfoTip label="核对范围">{{ value.scope }}</InfoTip></details></template>
