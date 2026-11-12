<script setup>defineOptions({inheritAttrs:false});import{ElImage}from'element-plus';import{ImageOff}from'@/components/app/icons.js';</script>
<template><ElImage fit="contain" class="app-element-image" v-bind="$attrs"><template #error><div class="element-image-error" role="img" :aria-label="$attrs.alt||'图片无法显示'"><ImageOff :size="22"/><span>图片无法显示</span></div></template></ElImage></template>
