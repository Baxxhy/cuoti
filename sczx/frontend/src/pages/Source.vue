<script setup>
import {useRoute} from 'vue-router';
import {useLearning} from '@/store.js';
import SourceReader from '@/components/SourceReader.vue';
const route=useRoute(),store=useLearning();
</script>
<template><PageHeading title="原文"><RouteButton :route="store.user?.role==='admin'?'manage':'cases'" secondary>返回资料</RouteButton></PageHeading><div class="ops-reading-sheet"><SourceReader :unit-id="String(route.query.unit || '')" /></div></template>
