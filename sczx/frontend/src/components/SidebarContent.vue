<script setup>
import {computed,inject,ref} from 'vue';
import {useRoute,useRouter} from 'vue-router';
import {ElMenu,ElMenuItem,ElAvatar} from 'element-plus';
import {BookOpenText,LogOut,CircleHelp,LayoutDashboard,NotebookPen,Users,LibraryBig,FileText,ClipboardList,Layers} from '@/components/app/icons.js';
import {useLearning} from '@/store.js';
import {workspaceGroups,workspaceFor} from '@/lib/workspace-navigation.js';
const route=useRoute(),router=useRouter(),shell=inject('shell'),store=useLearning();
const role=computed(()=>store.user?.role||'student');
const roleName=computed(()=>({student:'学生',teacher:'教师',admin:'管理员'})[role.value]);
const home=computed(()=>role.value==='teacher'?'teacher':role.value==='admin'?'manage':'home');
const userName=computed(()=>store.user?.displayName||'当前账号');
const active=computed(()=>workspaceFor(role.value,route.name)?.id);
const menu=ref();
const icons={learning:LayoutDashboard,review:NotebookPen,classroom:Users,overview:LayoutDashboard,resources:LibraryBig,planning:FileText,assessment:ClipboardList,materials:Layers,curriculum:BookOpenText,operations:ClipboardList};
async function openGroup(id){const group=workspaceGroups[role.value].find(item=>item.id===id);if(group){await router.push('/'+group.route);menu.value?.updateActiveIndex(active.value)}}
function activateOnKey(event,id){if(!['Enter',' '].includes(event.key)||event.ctrlKey||event.metaKey||event.altKey)return;event.preventDefault();event.stopPropagation();openGroup(id)}
</script>
<template>
 <a :href="'#/'+home" class="wordmark" aria-label="师承智学首页"><BookOpenText :size="25" :stroke-width="1.65"/><span>师承智学</span></a>
 <nav class="workspace-main-nav" aria-label="主要导航"><ElMenu ref="menu" :default-active="active" @select="openGroup"><ElMenuItem v-for="group in workspaceGroups[role]" :key="group.id" :index="group.id" @keydown="activateOnKey($event,group.id)"><a :href="'#/'+group.route" @click.stop :aria-current="active===group.id?'page':undefined"><component :is="icons[group.id]" :size="18"/><span>{{group.label}}</span></a></ElMenuItem></ElMenu></nav>
 <div class="sidebar-bottom"><AppButton variant="ghost" :class="['utility-button',{'is-current':route.name==='issues'&&role!=='admin'}]" @click="shell.openHelp()"><CircleHelp :size="17"/>帮助与反馈</AppButton><div class="profile"><ElAvatar :size="32">{{userName.slice(0,1)}}</ElAvatar><span><strong>{{userName}}</strong><small>{{roleName}}</small></span><AppButton variant="ghost" size="icon-sm" aria-label="退出登录" @click="shell.logout()"><LogOut :size="16"/></AppButton></div></div>
</template>
