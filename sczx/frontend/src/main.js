import { createApp } from "vue";
import { createPinia } from "pinia";
import { createRouter, createWebHashHistory } from "vue-router";
import "@fontsource-variable/geist";
import "./index.css";
import "./app.css";
import App from "./App.vue";
import Home from "./pages/Home.vue";
import Learning from "./pages/Learning.vue";
import Teacher from "./pages/Teacher.vue";
import Manage from "./pages/Manage.vue";
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
const groups = [
  [Home, ["home", "courses", "records", "teacher"]],
  [Learning, ["learn", "check", "result", "wrong", "repair"]],
  [Teacher, ["cases", "case-detail", "prepare", "class", "insights"]],
  [Manage, ["manage", "content", "issues"]],
];
const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: "/", redirect: "/home" },
    ...groups.flatMap(([component, names]) =>
      names.map((name) => ({ path: "/" + name, name, component })),
    ),
    { path: "/:pathMatch(.*)*", redirect: "/home" },
  ],
});
const app = createApp(App);
app.use(createPinia()).use(router);
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
store.$subscribe(() => store.save(), { detached: true, flush: "sync" });
app.mount("#root");
