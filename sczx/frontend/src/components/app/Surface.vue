<script setup>
import { computed, useAttrs } from 'vue';
import { ElCard } from 'element-plus';
const props=defineProps({bodyStyle:Object}),attrs=useAttrs();
const bodyStyle=computed(()=>attrs['data-ui']==='card'?{padding:'12px',...props.bodyStyle}:props.bodyStyle);
</script>
<template><ElCard class="surface" shadow="never" body-class="surface-body" :body-style="bodyStyle"><slot/></ElCard></template>
