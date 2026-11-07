<script setup>
defineProps({ title: String });
</script>
<template>
  <div class="page-heading">
    <h1>{{ title }}</h1>
    <div v-if="$slots.default" class="heading-actions"><slot /></div>
  </div>
</template>
