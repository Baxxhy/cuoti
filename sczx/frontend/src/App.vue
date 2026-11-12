<script setup>
import {statusTone} from "@/lib/status-tone.js";
import {navigation as routeNavigation} from "@/lib/navigation-items.js";
import {workspaceFor} from "@/lib/workspace-navigation.js";
import WorkspaceNavigation from "@/components/WorkspaceNavigation.vue";
import {platformDraft} from '@/lib/platform-persistence.js';
import { computed, onMounted, onBeforeUnmount, provide, ref, watch } from "vue";
import { useRoute } from "vue-router";
import UiProvider from "@/components/app/Provider.vue";
import {ElMessage} from "element-plus";
import {BookOpen,BookOpenText,Search,Bell,Menu,ArrowUpRight,ArrowLeft} from "@/components/app/icons.js";
import { navigate } from "@/lib/navigation.js";
import SidebarContent from "@/components/SidebarContent.vue";
import { useLearning } from "@/store.js";
import MessageCenter from "@/components/MessageCenter.vue";
import PlatformStatus from "@/components/PlatformStatus.vue";
import NotFound from "@/pages/NotFound.vue";
const store = useLearning();
const route = useRoute();
const missingTask = computed(
  () =>
    store.status === "ready" &&
    !!route.query.task &&
    !store.data.tasks.some((task) => task.id === route.query.task),
);
const missingWrong = computed(() => false);
watch(
  [() => store.status, () => route.query.task],
  () => {
    if (store.status === "ready" && route.query.task)
      store.selectTask(route.query.task);
  },
  { immediate: true },
);

const navigation=Object.fromEntries(Object.entries(routeNavigation).map(([role,items])=>[role,items.map(([route,label,icon])=>({route,label,icon}))]));
const role = computed(() => store.user?.role || "student");
const currentWorkspace=computed(()=>workspaceFor(role.value,route.name));
const studyFocus=computed(()=>role.value==='student'&&['learn','check','repair'].includes(route.name));
const active = computed(
  () =>
    ({
      exams: role.value==='teacher'?'exam-papers':'exams',
      learn: "home",
      check: "home",
      result: "home",
      repair: "wrong",
      "case-detail": "cases",
      agent: "prepare",
      insights: "class",
    })[route.name] || route.name,
);
const pageLabel = computed(
  () =>
    (route.name === "source" ? "原文阅读" : route.name === "agent" ? "任务备课" : navigation[role.value].find((item) => item.route === active.value)?.label) ||
    "学习工作区",
);
const pageKey = current => ['manage','content','insights'].includes(current.name) ? current.path : current.fullPath;
const notice = ref("");
const mobileOpen = ref(false);
const searchOpen = ref(false);
const notifications = ref(false);

const search = ref("");

let messageHandle;
const notify = (message) => {
  notice.value=message;
  messageHandle?.close();
  messageHandle=ElMessage({message:String(message),type:({success:'success',danger:'error',pending:'warning'})[statusTone(message)]||'info',showClose:true,duration:3500});
};
provide("notify", notify);
provide("shell", {
  openHelp: () => {
    mobileOpen.value=false;navigate('issues'+(role.value==='admin'?'?section=queue':''));
  },
  logout: async () => {
    try {
      await store.logout();
      navigate("login");
    } catch (error) {
      notify(error.message);
    }
  },
});
watch(notice, (message, old, onCleanup) => {
  if (!message) return;
  const timer = window.setTimeout(() => {
    notice.value = "";
  }, 3500);
  onCleanup(() => window.clearTimeout(timer));
});
watch(
  () => route.fullPath,
  () => {
    mobileOpen.value = false;
    window.scrollTo(0, 0);
    document.title = `${pageLabel.value} 　 师承智学`;
  },
);
function focusContent(){ document.getElementById('main-content')?.focus(); }
function downloadDraft(){
 const backup={schema:1,kind:'sczx-unsaved-draft',ownerId:store.user.id,at:new Date().toISOString(),data:platformDraft(store.data,store.user.role)};
 const url=URL.createObjectURL(new Blob([JSON.stringify(backup,null,2)],{type:'application/json'})),link=document.createElement('a');
 link.href=url;link.download='未保存草稿.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function keyboard(event) {
  if ((event.metaKey || event.ctrlKey) && event.key === "k") {
    event.preventDefault();
    searchOpen.value = true;
  }
}
onMounted(() => window.addEventListener("keydown", keyboard));
onBeforeUnmount(() => {window.removeEventListener("keydown", keyboard);messageHandle?.close()});
const results = computed(() => {
  const items = navigation[role.value].map(item => ({route:item.route,title:item.label,subtitle:''}));
  if(role.value==='student') for(const task of store.data.tasks||[]) items.push({route:'learn?task='+task.id,title:task.title,subtitle:task.className||'学习任务'});
  if(role.value==='teacher') for(const item of store.data.cases||[]) items.push({route:'case-detail?caseId='+item.id,title:item.title,subtitle:'教学案例'});
  return items.filter(item=>(item.title+item.subtitle).includes(search.value.trim())).slice(0,12);
});
</script>
<template>
  <UiProvider>
      <RouterView v-if="!store.user" />
      <div v-else :class="['app-shell',{'is-study':studyFocus}]">
        <ElLink :underline="false" href="#main-content" class="skip-link" @click.prevent="focusContent()">跳至主要内容</ElLink>
        <ElAside width="216px" v-if="!studyFocus" class="desktop-sidebar"><SidebarContent /></ElAside>
        <ElContainer direction="vertical" class="app-body">
          <ElHeader v-if="studyFocus" class="study-topbar"><ElLink :underline="false" href="#/home"><ArrowLeft :size="17"/>我的学习</ElLink><ElLink :underline="false" href="#/home" class="study-brand"><BookOpenText :size="22"/>师承智学</ElLink><AppButton variant="ghost" @click="mobileOpen=true"><Menu :size="17"/>导航</AppButton></ElHeader>
          <ElHeader v-else class="topbar">
            <div class="topbar-start">
              <AppButton
                variant="ghost"
                size="icon"
                class="mobile-menu"
                aria-label="打开导航菜单"
                @click="mobileOpen = true"
                ><Menu /></AppButton
              ><span class="topbar-breadcrumb"
                ><strong>{{ currentWorkspace?.label || pageLabel }}</strong></span
              >
            </div>
            <div class="topbar-actions">
              <AppButton
                variant="ghost"
                class="search-trigger"
                aria-label="搜索页面与任务"
                @click="searchOpen = true"
                ><Search :size="16" /><span>搜索页面、任务</span
                ><ElTag size="small" effect="plain" aria-label="搜索快捷键">⌘ K</ElTag></AppButton
              ><AppButton
                variant="ghost"
                size="icon"
                class="notification-trigger"
                aria-label="查看消息"
                @click="notifications = true"
                ><ElBadge :value="store.unreadCount" :hidden="!store.unreadCount"><Bell :size="18"/></ElBadge></AppButton
              ><ElBadge is-dot :type="store.status==='ready'?'success':'warning'" :aria-label="store.status==='ready'?'服务已连接':'正在连接服务'" role="status"><span class="connection-anchor" aria-hidden="true"/></ElBadge>
            </div>
          </ElHeader>
          <ElMain id="main-content" tabindex="-1">
            <AppAlert type="error" v-if="store.saveError && route.name!=='prepare'" class="save-error" role="alert">
              <span>{{ store.saveError }}</span
              ><AppButton
                variant="outline"
                size="sm"
                :disabled="store.saving"
                @click="store.save"
                >重新保存</AppButton
              ><AppButton variant="outline" @click="downloadDraft">下载未保存草稿</AppButton>
            </AppAlert>
            <PlatformStatus
              v-if="store.status !== 'ready' && route.name !== 'issues'"
            />
            <ElContainer v-else-if="missingTask || missingWrong" direction="vertical" class="page-content">
              <NotFound />
            </ElContainer>
            <RouterView v-else v-slot="{ Component, route: currentRoute }"
              ><ElContainer direction="vertical"
                  :key="pageKey(currentRoute)"
                  class="page-content"
                  ><WorkspaceNavigation v-if="!studyFocus"/><component
                    :is="Component"
                    :key="
                      pageKey(currentRoute)
                    " /></ElContainer></RouterView>
          </ElMain>
        </ElContainer>
      </div>
      <AppDialog
        v-model:open="mobileOpen"
        title="主要导航"
        content-class="mobile-sidebar"
        ><SidebarContent
      /></AppDialog>
      <AppDialog
        v-model:open="searchOpen"
        title="搜索学习内容"
        content-class="search-dialog"
        ><Input
          v-model="search"
          placeholder="输入页面或任务名称"
          aria-label="搜索内容"
        />
        <div class="search-results">
          <AppButton variant="ghost" data-layout="row" type="button"
            v-for="item in results"
            :key="item.route"
            @click="
              navigate(item.route);
              searchOpen = false;
            "
          >
            <BookOpen :size="20" /><span
              ><strong>{{ item.title }}</strong
              ><small>{{ item.subtitle }}</small></span
            ><ArrowUpRight :size="17" />
          </AppButton>
          <p v-if="!results.length" class="muted">没有匹配结果</p>
        </div></AppDialog
      >
      <AppDialog v-model:open="notifications" title="消息与提醒"><MessageCenter @navigate="notifications=false"/></AppDialog
      >
    </UiProvider>
</template>
