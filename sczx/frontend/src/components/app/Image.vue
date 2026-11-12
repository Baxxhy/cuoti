<script setup>
defineOptions({inheritAttrs:false});
import { ElImage } from 'element-plus';
</script>
<template><ElImage fit="contain" class="app-element-image" v-bind="$attrs" :aria-label="$attrs.alt"/></template>
