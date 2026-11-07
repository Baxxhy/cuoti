<script setup>
import { computed, onMounted, onBeforeUnmount, provide, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { AnimatePresence, motion, MotionConfig } from "motion-v";
import { TooltipProvider } from "@/components/ui/tooltip/index.js";
import {
  BookOpen,
  BookOpenText,
  LayoutDashboard,
  NotebookPen,
  History,
  LibraryBig,
  Users,
  FileText,
  Settings2,
  Search,
  Bell,
  Menu,
  ArrowUpRight,
  CircleHelp,
  Check,
  GraduationCap,
  Layers,
  MessageSquareText,
} from "lucide-vue-next";
import { navigate } from "@/lib/navigation.js";
import SidebarContent from "@/components/SidebarContent.vue";
import { useLearning } from "@/store.js";
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
const missingWrong = computed(
  () =>
    store.status === "ready" &&
    !!route.query.wrong &&
    !store.record?.wrongQuestions.some((item) => item.id === route.query.wrong),
);
watch(
  [() => store.status, () => route.query.task],
  () => {
    if (store.status === "ready" && route.query.task)
      store.selectTask(route.query.task);
  },
  { immediate: true },
);

const navigation = {
  student: [
    { route: "home", label: "我的学习", icon: LayoutDashboard },
    { route: "courses", label: "探索课程", icon: BookOpen },
    { route: "wrong", label: "错题帮", icon: NotebookPen },
    { route: "records", label: "学习记录", icon: History },
  ],
  teacher: [
    { route: "teacher", label: "教学概览", icon: LayoutDashboard },
    { route: "cases", label: "教学案例", icon: LibraryBig },
    { route: "prepare", label: "我的教案", icon: FileText },
    { route: "class", label: "班级教学", icon: Users },
  ],
  admin: [
    { route: "manage", label: "内容工作台", icon: Layers },
    { route: "content", label: "课程内容", icon: BookOpenText },
    { route: "issues", label: "反馈与运行", icon: MessageSquareText },
  ],
};
const roleOptions = [
  { value: "student", label: "学生空间" },
  { value: "teacher", label: "教师空间" },
  { value: "admin", label: "内容管理" },
];
const role = computed({
  get: () =>
    [
      "teacher",
      "cases",
      "case-detail",
      "prepare",
      "class",
      "insights",
    ].includes(route.name)
      ? "teacher"
      : ["manage", "content", "issues"].includes(route.name)
        ? "admin"
        : "student",
  set: (value) =>
    navigate(
      value === "teacher" ? "teacher" : value === "admin" ? "manage" : "home",
    ),
});
const roleLabel = computed(
  () => roleOptions.find((item) => item.value === role.value).label,
);
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
const pageLabel = computed(
  () =>
    navigation[role.value].find((item) => item.route === active.value)?.label ||
    "学习工作区",
);
const notice = ref("");
const mobileOpen = ref(false);
const searchOpen = ref(false);
const notifications = ref(false);
const helpOpen = ref(false);
const search = ref("");
const issueNote = ref("");
const notify = (message) => {
  notice.value = message;
};
provide("notify", notify);
provide("shell", {
  openHelp: () => {
    helpOpen.value = true;
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
    document.title = `${pageLabel.value} · 师承智学`;
  },
);
function keyboard(event) {
  if ((event.metaKey || event.ctrlKey) && event.key === "k") {
    event.preventDefault();
    searchOpen.value = true;
  }
}
onMounted(() => window.addEventListener("keydown", keyboard));
onBeforeUnmount(() => window.removeEventListener("keydown", keyboard));
const results = computed(() =>
  [
    { route: "learn", title: "等式性质", subtitle: "七年级数学 · 第 1 课" },
    { route: "wrong", title: "错题帮", subtitle: "错题记录" },
    { route: "cases", title: "天平与等式 · 教学案例", subtitle: "教学案例" },
  ].filter((item) => (item.title + item.subtitle).includes(search.value)),
);
function submitFeedback() {
  if (!issueNote.value.trim()) return notify("请填写反馈");
  store.data.issue.text = issueNote.value;
  store.data.issue.resolved = false;
  store.data.issue.reply = "";
  store.touch();
  helpOpen.value = false;
  notify("体验反馈已记录");
}
</script>
<template>
  <MotionConfig reduced-motion="user"
    ><TooltipProvider :delay-duration="100">
      <div class="app-shell">
        <aside class="desktop-sidebar"><SidebarContent /></aside>
        <div class="app-body">
          <header class="topbar">
            <div class="topbar-start">
              <Button
                variant="ghost"
                size="icon"
                class="mobile-menu"
                aria-label="打开导航菜单"
                @click="mobileOpen = true"
                ><Menu /></Button
              ><span class="topbar-breadcrumb"
                >{{ roleLabel }}<span>/</span
                ><strong>{{ pageLabel }}</strong></span
              >
            </div>
            <div class="topbar-actions">
              <Button
                variant="ghost"
                class="search-trigger"
                aria-label="搜索课程和案例"
                @click="searchOpen = true"
                ><Search :size="16" /><span>搜索课程、案例</span
                ><kbd>⌘ K</kbd></Button
              ><Button
                variant="ghost"
                size="icon"
                aria-label="查看消息"
                @click="notifications = true"
                ><Bell :size="18" /></Button
              ><span class="topbar-demo"
                >演示<InfoTip label="演示范围"
                  >数据为演示；模型生成和发布采用本地模拟，学习记录保存在当前浏览器。</InfoTip
                ></span
              >
            </div>
          </header>
          <main>
            <div v-if="store.saveError" class="save-error" role="alert">
              <span>{{ store.saveError }}</span
              ><Button
                variant="outline"
                size="sm"
                :disabled="store.saving"
                @click="store.save"
                >重新保存</Button
              ><RouteButton route="issues" secondary>导出记录</RouteButton>
            </div>
            <PlatformStatus
              v-if="store.status !== 'ready' && route.name !== 'issues'"
            />
            <div v-else-if="missingTask || missingWrong" class="page-content">
              <NotFound />
            </div>
            <RouterView v-else v-slot="{ Component, route: currentRoute }"
              ><AnimatePresence mode="wait"
                ><motion.div
                  :key="currentRoute.fullPath"
                  class="page-content"
                  :initial="{ opacity: 0, y: 9 }"
                  :animate="{ opacity: 1, y: 0 }"
                  :exit="{ opacity: 0, y: -4 }"
                  :transition="{ duration: 0.2 }"
                  ><component
                    :is="Component"
                    :key="
                      currentRoute.fullPath
                    " /></motion.div></AnimatePresence
            ></RouterView>
          </main>
        </div>
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
          placeholder="试试“等式”或“天平”"
          aria-label="搜索内容"
        />
        <div class="search-results">
          <button
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
          </button>
          <p v-if="!results.length" class="muted">没有匹配结果</p>
        </div></AppDialog
      >
      <AppDialog v-model:open="notifications" title="消息与提醒"
        ><button
          v-for="message in store.data.messages"
          :key="message.id"
          class="notification-row"
          @click="
            navigate(`result?task=${message.taskId}`);
            notifications = false;
          "
        >
          <span class="notification-dot" /><strong>{{ message.title }}</strong
          ><ArrowUpRight :size="16" />
        </button>
        <p v-if="!store.data.messages.length" class="muted">
          暂无消息
        </p></AppDialog
      ><AppDialog v-model:open="helpOpen" title="帮助与反馈"
        ><label class="field-label" for="issue-note">体验反馈</label
        ><Textarea
          id="issue-note"
          v-model="issueNote"
          placeholder="填写反馈"
        /><Button @click="submitFeedback">记录反馈</Button></AppDialog
      >
      <AnimatePresence
        ><motion.div
          v-if="notice"
          class="toast-message"
          role="status"
          :initial="{ opacity: 0, y: 20 }"
          :animate="{ opacity: 1, y: 0 }"
          :exit="{ opacity: 0, y: 10 }"
          ><Check :size="16" />{{ notice }}</motion.div
        ></AnimatePresence
      >
    </TooltipProvider></MotionConfig
  >
</template>
