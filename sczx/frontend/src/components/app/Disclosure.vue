<script setup>
import { ref, watch } from 'vue';
import { ElCollapse, ElCollapseItem } from 'element-plus';
const emit = defineEmits(['change']);
const props = defineProps({ open: Boolean });
const expanded = ref(props.open ? ['content'] : []);
watch(() => props.open, value => { expanded.value = value ? ['content'] : []; });
</script>
<template><ElCollapse v-model="expanded" @change="value => emit('change', value.length > 0)" class="app-element-collapse"><ElCollapseItem name="content"><template #title><slot name="title"/></template><slot/></ElCollapseItem></ElCollapse></template>
