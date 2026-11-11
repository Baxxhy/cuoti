<script setup>
import {navigation} from "@/lib/navigation-items.js";
import { computed, inject } from "vue";
import { useRoute } from "vue-router";
import {
  BookOpen,
  BookOpenText,
  LayoutDashboard,
  NotebookPen,
  History,
  LibraryBig,
  Users,
  FileText,
  LogOut,
  CircleHelp,
  GraduationCap,
  Layers,
  MessageSquareText,
} from "lucide-vue-next";
import { useLearning } from "@/store.js";
const route = useRoute();
const shell = inject("shell");
const store = useLearning();
const role = computed(() => store.user?.role || "student");
const roleName = computed(() => ({ student: "学生空间", teacher: "教学空间", admin: "工作空间" })[role.value]);
const userName = computed(() => store.user?.displayName || "当前账号");
const initial = computed(() => userName.value.slice(0, 1));
const active = computed(
  () =>
    ({
      learn: "home",
      check: "home",
      result: "home",
      repair: "wrong",
      "case-detail": "cases",
      insights: "class",
    })[route.name] || route.name,
);
const items = computed(()=>navigation[role.value]);
</script>
<template>
  <a href="#/home" class="wordmark" aria-label="师承智学首页"
    ><span class="brand-symbol"
      ><BookOpenText :size="23" :stroke-width="1.8" /></span
    ><span>师承智学</span></a
  >
  <div class="workspace-switch"><span class="role-pill">{{ roleName }}</span></div>
  <div class="nav-label">
    {{
      role === "student"
        ? "学习空间"
        : role === "teacher"
          ? "教学空间"
          : "工作空间"
    }}
  </div>
  <nav aria-label="主要导航">
    <a
      v-for="item in items"
      :key="item[0]"
      :href="`#/${item[0]}`"
      :class="['nav-item', { active: active === item[0] }]"
      :aria-current="active === item[0] ? 'page' : undefined"
      ><component :is="item[2]" :size="18" :stroke-width="1.7" /><span>{{
        item[1]
      }}</span
      ><span v-if="active === item[0]" class="nav-dot"
    /></a>
  </nav>
  <div class="sidebar-bottom">
    <Button variant="ghost" class="utility-button" @click="shell.openHelp()"
      ><CircleHelp />帮助与反馈</Button
    >
    <div class="profile">
      <span class="avatar">{{ initial }}</span
      ><span><strong>{{ userName }}</strong></span
      ><Button
        variant="ghost"
        size="icon-sm"
        aria-label="退出登录"
        @click="shell.logout()"
        ><LogOut
      /></Button>
    </div>
  </div>
</template>
