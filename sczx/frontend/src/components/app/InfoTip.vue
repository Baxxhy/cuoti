<script setup>
import{ElTooltip,ElButton}from'element-plus';import{Info}from'lucide-vue-next';defineProps({label:String});
</script>
<template><ElTooltip placement="top" :show-after="150" effect="dark" popper-class="app-info-tooltip"><template #content><slot/></template><ElButton class="info-tip" text circle :aria-label="label" native-type="button"><Info :size="15"/></ElButton></ElTooltip></template>
