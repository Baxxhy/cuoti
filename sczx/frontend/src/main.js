import LearningMemory from './pages/LearningMemory.vue';
import SourcePage from './pages/Source.vue';
import { createApp, watch } from "vue";
import { createPinia } from "pinia";
import { createRouter, createWebHashHistory } from "vue-router";
import "@fontsource-variable/geist";
import "./index.css";
import "./app.css";
import App from "./App.vue";
import Dashboard from "./pages/Dashboard.vue";
import Courses from "./pages/Courses.vue";
import Records from "./pages/Records.vue";
import Lesson from "./pages/Lesson.vue";
import CheckLesson from "./pages/CheckLesson.vue";
import Result from "./pages/Result.vue";
import WrongQuestions from "./pages/WrongQuestions.vue";
import Repair from "./pages/Repair.vue";
import Cases from "./pages/Cases.vue";
import CaseDetail from "./pages/CaseDetail.vue";
import Prepare from "./pages/Prepare.vue";
import PlanningAgent from "./pages/PlanningAgent.vue";
import Classroom from "./pages/Classroom.vue";
import Insights from "./pages/Insights.vue";
import ManageContent from "./pages/ManageContent.vue";
import CourseContent from "./pages/CourseContent.vue";
import Issues from "./pages/Issues.vue";
import NotFound from "./pages/NotFound.vue";
import Login from "./pages/Login.vue";
import Button from "./components/app/Button.vue";
import Surface from "./components/app/Surface.vue";
import PageHeading from "./components/app/PageHeading.vue";
import SectionHeading from "./components/app/SectionHeading.vue";
import RouteButton from "./components/app/RouteButton.vue";
import Status from "./components/app/Status.vue";
import InfoTip from "./components/app/InfoTip.vue";
import AppDialog from "./components/app/Dialog.vue";
import AppSelect from "./components/app/Select.vue";
import AppTabs from "./components/app/Tabs.vue";
import ExperienceLink from "./components/app/ExperienceLink.vue";
import { Input } from "./components/ui/input/index.js";
import { Textarea } from "./components/ui/textarea/index.js";
import { Progress } from "./components/ui/progress/index.js";
import { useLearning } from "./store.js";
// Existing bookmarked prototype URLs used #home; retain their entry behavior.
if (location.hash && !location.hash.startsWith("#/"))
  history.replaceState(null, "", "#/" + location.hash.slice(1));
const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: "/", redirect: "/home" },
    { path: "/login", name: "login", component: Login, meta: { public: true } },
    { path: "/home", name: "home", component: Dashboard },
    { path: "/teacher", name: "teacher", component: Dashboard },
    { path: "/courses", name: "courses", component: Courses },
    { path: "/memory", name: "memory", component: LearningMemory },
    { path: "/records", name: "records", component: Records },
    { path: "/learn", name: "learn", component: Lesson },
    { path: "/check", name: "check", component: CheckLesson },
    { path: "/result", name: "result", component: Result },
    { path: "/wrong", name: "wrong", component: WrongQuestions },
    { path: "/repair", name: "repair", component: Repair },
    { path: "/cases", name: "cases", component: Cases },
    { path: "/source", name: "source", component: SourcePage },
    { path: "/case-detail", name: "case-detail", component: CaseDetail },
    { path: "/prepare", name: "prepare", component: Prepare },
    { path: "/agent", name: "agent", component: PlanningAgent },
    { path: "/class", name: "class", component: Classroom },
    { path: "/insights", name: "insights", component: Insights },
    { path: "/manage", name: "manage", component: ManageContent },
    { path: "/content", name: "content", component: CourseContent },
    { path: "/issues", name: "issues", component: Issues },
    { path: "/:pathMatch(.*)*", name: "not-found", component: NotFound },
  ],
});
const app = createApp(App);
const pinia = createPinia();
app.use(pinia);
for (const [name, component] of Object.entries({
  Button,
  Surface,
  PageHeading,
  SectionHeading,
  RouteButton,
  Status,
  InfoTip,
  AppDialog,
  AppSelect,
  AppTabs,
  ExperienceLink,
  Input,
  Textarea,
  Progress,
}))
  app.component(name, component);
const store = useLearning();
let sessionReady;
const roleRoutes = {
  student: new Set(["memory", "source", "home", "class", "courses", "records", "learn", "check", "result", "wrong", "repair", "issues"]),
  teacher: new Set(["memory", "source", "teacher", "courses", "cases", "case-detail", "prepare", "agent", "class", "insights", "issues"]),
  admin: new Set(["source", "manage", "content", "issues", "cases", "case-detail", "courses"]),
};
router.beforeEach(async (to) => {
  if (to.name === "login") {
    if (!sessionReady) sessionReady = store.initialize();
    await sessionReady;
    if (store.user) return { name: store.user.role === "teacher" ? "teacher" : store.user.role === "admin" ? "manage" : "home" };
    return true;
  }
  if (!sessionReady) sessionReady = store.initialize();
  await sessionReady;
  if (!store.user) return { name: "login", query: { next: to.fullPath } };
  if (!roleRoutes[store.user.role]?.has(to.name)) return { name: store.user.role === "teacher" ? "teacher" : store.user.role === "admin" ? "manage" : "home" };
  if (store.status === "ready" && store.data) {
    const saved = await store.save();
    if (!saved && to.name !== router.currentRoute.value.name) return false;
  }
  return true;
});
let saveTimer;
watch(
  () => { const draft={...store.data.lessonDraft}; delete draft.revision; return JSON.stringify({...store.data,lessonDraft:draft}); },
  () => {
    if (store.status !== "ready" || !store.user || store.externalUpdating) return;
    store.revision++;
    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => { if (!store.externalUpdating) store.save(); }, 300);
  },
  { deep: true },
);
app.use(router);
app.mount("#root");
