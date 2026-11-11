<script setup>
import {useRoute} from 'vue-router';
import {useLearning} from '@/store.js';
import SourceReader from '@/components/SourceReader.vue';
import {computed} from 'vue';
const route=useRoute(),store=useLearning();
const back=computed(()=>store.user?.role==='admin'?'manage':store.user?.role==='teacher'?'cases':store.task?'learn?task='+store.task.id:'home');
</script>
<template><PageHeading title="原文"><RouteButton :route="back" secondary>{{store.user?.role==='student'?'返回学习':'返回资料'}}</RouteButton></PageHeading><div class="ops-reading-sheet"><SourceReader :unit-id="String(route.query.unit || '')" /></div></template>
