<script setup>
import {computed} from 'vue';
import {useRoute} from 'vue-router';
import {useLearning} from '@/store.js';
import {workspaceFor,workspaceHref} from '@/lib/workspace-navigation.js';
const props=defineProps({role:String,routeName:String});const route=useRoute(),store=useLearning();
const role=computed(()=>props.role||store.user?.role);
const current=computed(()=>props.routeName||route.name);
const group=computed(()=>workspaceFor(role.value,current.value));
const active=computed(()=>({'case-detail':'cases'})[current.value]||current.value);
function href(target){return target===current.value?'#'+route.fullPath:workspaceHref(role.value,target,route.query,store.currentClassId)}
</script>
<template><nav v-if="group?.tabs.length>1" class="workspace-section-nav" :aria-label="group.label+'分类'"><a v-for="[target,label] in group.tabs" :key="target" :href="href(target)" :aria-current="active===target?'page':undefined">{{label}}</a></nav></template>
