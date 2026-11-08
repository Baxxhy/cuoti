<script setup>
import {useRoute} from 'vue-router';
import SourceReader from '@/components/SourceReader.vue';
const route=useRoute();
</script>
<template><PageHeading title="原文阅读" /><SourceReader :unit-id="String(route.query.unit || '')" /></template>
