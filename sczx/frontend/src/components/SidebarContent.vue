<script setup>
import {computed,inject} from 'vue';
import {useRoute} from 'vue-router';
import {BookOpenText,LogOut,CircleHelp,LayoutDashboard,NotebookPen,Users,LibraryBig,FileText,ClipboardList,Layers} from 'lucide-vue-next';
import {useLearning} from '@/store.js';
import {workspaceGroups,workspaceFor} from '@/lib/workspace-navigation.js';
const route=useRoute(),shell=inject('shell'),store=useLearning();
const role=computed(()=>store.user?.role||'student');
const roleName=computed(()=>({student:'学生',teacher:'教师',admin:'管理员'})[role.value]);
const home=computed(()=>role.value==='teacher'?'teacher':role.value==='admin'?'manage':'home');
const userName=computed(()=>store.user?.displayName||'当前账号');
const active=computed(()=>workspaceFor(role.value,route.name)?.id);
const icons={learning:LayoutDashboard,review:NotebookPen,classroom:Users,overview:LayoutDashboard,resources:LibraryBig,planning:FileText,assessment:ClipboardList,materials:Layers,curriculum:BookOpenText,operations:ClipboardList};
</script>
<template>
 <a :href="'#/'+home" class="wordmark" aria-label="师承智学首页"><BookOpenText :size="25" :stroke-width="1.65"/><span>师承智学</span></a>
 <nav class="workspace-main-nav" aria-label="主要导航"><a v-for="group in workspaceGroups[role]" :key="group.id" :href="'#/'+group.route" :class="['nav-item',{active:active===group.id}]" :aria-current="active===group.id?'page':undefined"><component :is="icons[group.id]" :size="17" :stroke-width="1.65"/><span>{{group.label}}</span></a></nav>
 <div class="sidebar-bottom"><AppButton variant="ghost" :class="['utility-button',{'is-current':route.name==='issues'&&role!=='admin'}]" @click="shell.openHelp()"><CircleHelp :size="17"/>帮助与反馈</AppButton><div class="profile"><span class="avatar">{{userName.slice(0,1)}}</span><span><strong>{{userName}}</strong><small>{{roleName}}</small></span><AppButton variant="ghost" size="icon-sm" aria-label="退出登录" @click="shell.logout()"><LogOut :size="16"/></AppButton></div></div>
</template>
