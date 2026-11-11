<script setup>
import { navigation } from '@/lib/navigation-items.js';
import { computed, inject, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { BookOpenText, LogOut, CircleHelp, ChevronDown } from 'lucide-vue-next';
import { useLearning } from '@/store.js';
const route=useRoute(), shell=inject('shell'), store=useLearning();
const role=computed(()=>store.user?.role||'student');
const roleName=computed(()=>({student:'学生',teacher:'教师',admin:'管理员'})[role.value]);
const home=computed(()=>role.value==='teacher'?'teacher':role.value==='admin'?'manage':'home');
const userName=computed(()=>store.user?.displayName||'当前账号');
const active=computed(()=>({exams:role.value==='teacher'?'exam-papers':'exams',learn:'home',check:'home',result:'home',repair:'wrong','case-detail':'cases',agent:'prepare',insights:'class'})[route.name]||route.name);
const primaryKeys={student:['home','courses','wrong','exams','live'],teacher:['teacher','prepare','cases','class','exam-papers','live'],admin:['manage','content','issues']};
const primary=computed(()=>navigation[role.value].filter(i=>primaryKeys[role.value].includes(i[0])));
const secondary=computed(()=>navigation[role.value].filter(i=>!primaryKeys[role.value].includes(i[0])));
const moreOpen=ref(false);
watch(active,key=>{if(secondary.value.some(i=>i[0]===key))moreOpen.value=true},{immediate:true});
</script>
<template>
  <a :href="'#/'+home" class="wordmark" aria-label="师承智学首页"><BookOpenText :size="25" :stroke-width="1.65"/><span>师承智学</span></a>
  <div class="workspace-identity"><span>{{ roleName }}工作区</span></div>
  <nav aria-label="主要导航">
    <a v-for="item in primary" :key="item[0]" :href="'#/'+item[0]" :class="['nav-item',{active:active===item[0]}]" :aria-current="active===item[0]?'page':undefined"><component :is="item[2]" :size="17" :stroke-width="1.65"/><span>{{ item[1] }}</span></a>
    <details v-if="secondary.length" :open="moreOpen" class="navigation-more" @toggle="moreOpen=$event.target.open">
      <summary>更多功能<ChevronDown :size="14"/></summary>
      <a v-for="item in secondary" :key="item[0]" :href="'#/'+item[0]" :class="['nav-item',{active:active===item[0]}]" :aria-current="active===item[0]?'page':undefined"><component :is="item[2]" :size="17" :stroke-width="1.65"/><span>{{ item[1] }}</span></a>
    </details>
  </nav>
  <div class="sidebar-bottom"><Button variant="ghost" class="utility-button" @click="shell.openHelp()"><CircleHelp :size="17"/>帮助与反馈</Button><div class="profile"><span class="avatar">{{userName.slice(0,1)}}</span><span><strong>{{userName}}</strong><small>{{roleName}}</small></span><Button variant="ghost" size="icon-sm" aria-label="退出登录" @click="shell.logout()"><LogOut :size="16"/></Button></div></div>
</template>
