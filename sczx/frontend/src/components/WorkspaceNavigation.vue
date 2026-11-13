<script setup>
import {computed,ref,watch} from 'vue';
import {useRoute,useRouter} from 'vue-router';
import {ElTabs,ElTabPane} from 'element-plus';
import {useLearning} from '@/store.js';
import {workspaceFor,workspaceHref} from '@/lib/workspace-navigation.js';
const props=defineProps({role:String,routeName:String});const route=useRoute(),router=useRouter(),store=useLearning();
const role=computed(()=>props.role||store.user?.role);
const current=computed(()=>props.routeName||route.name);
const group=computed(()=>workspaceFor(role.value,current.value));
const active=computed(()=>({'case-detail':'cases'})[current.value]||current.value);
const selected=ref(active.value);
watch(active,value=>{selected.value=value});
function href(target){return target===current.value?'#'+route.fullPath:workspaceHref(role.value,target,route.query,store.currentClassId)}
async function changeTab(target){await router.push(href(target).slice(1));selected.value=active.value}
</script>
<template><ElTabs v-if="group?.tabs.length>1" class="workspace-section-nav" :aria-label="group.label+'分类'" v-model="selected" @tab-change="changeTab"><ElTabPane v-for="[target,label] in group.tabs" :key="target" :name="target"><template #label><ElLink :underline="false" :href="href(target)" @click.stop :aria-current="active===target?'page':undefined">{{label}}</ElLink></template></ElTabPane></ElTabs></template>
