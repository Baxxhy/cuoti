<script setup>
import { ref, computed, onMounted, watch, onBeforeUnmount } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useLearning } from "@/store.js";
import { teachingApi, deadlineText } from "@/services/teaching.js";
import TaskList from "@/components/TaskList.vue";
import MessageCenter from "@/components/MessageCenter.vue";
import { ArrowRight, Users, BookOpen, Inbox } from "lucide-vue-next";
const store = useLearning(),
  route = useRoute(),
  router = useRouter(),
  teacher = computed(() => route.name === "teacher"),
  overview = ref(null),
  error = ref(""),
  loading = ref(true),
  selected = ref(
    String(
      route.query.class ||
        store.currentClassId ||
        store.data.classroom?.id ||
        "",
    ),
  );
let generation = 0;
async function load() {
  const g = ++generation;
  loading.value = true;
  error.value = "";
  overview.value = null;
  try {
    const value = await teachingApi.dashboard(
      teacher.value ? selected.value : undefined,
    );
    if (g !== generation) return;
    overview.value = value;
    if (teacher.value) {
      selected.value = value.selectedClassId || "";
      store.currentClassId = selected.value;
      store.data.publishClassId = selected.value;
    }
  } catch (e) {
    if (g === generation) error.value = e.message;
  } finally {
    if (g === generation) loading.value = false;
  }
}
watch(
  () => route.query.class,
  (id) => {
    if (teacher.value && id && id !== selected.value) {
      selected.value = String(id);
      load();
    }
  },
);
onMounted(load);
async function select() {
  await router.replace({
    query: { ...route.query, class: selected.value || undefined },
  });
  load();
}
onBeforeUnmount(() => {
  generation++;
});
</script>
<template>
  <PageHeading :title="teacher ? '教学概览' : '我的学习'"
    ><RouteButton
      v-if="teacher"
      :route="'prepare' + (selected ? '?class=' + selected : '')"
      >备课并发布</RouteButton
    ><RouteButton v-else route="class" secondary
      >我的班级</RouteButton
    ></PageHeading
  >
  <p v-if="error" class="form-error" role="alert">{{ error }}</p>
  <div
    v-if="teacher && overview?.classes.length"
    class="teaching-class-toolbar"
  >
    <AppSelect
      v-model="selected"
      label="概览班级"
      :options="overview.classes.map((c) => ({ value: c.id, label: c.name }))"
      @update:model-value="select"
    />
  </div>
  <p v-if="loading" role="status">读取中…</p>
  <template v-if="overview"
    ><div class="teaching-metrics">
      <Surface
        v-for="(label, key) in teacher
          ? {
              tasks: '班级任务',
              unsubmittedStudents: '未提交学生',
              waitingFeedback: '待反馈记录',
            }
          : { pending: '待完成', inProgress: '学习中', submitted: '已提交' }"
        :key="key"
        ><span>{{ label }}</span
        ><strong>{{ overview.stats[key] || 0 }}</strong></Surface
      >
    </div>
    <div class="teaching-dashboard">
      <main>
        <section class="lesson-hero">
          <img src="/images/equation-balance.png" alt="数学课程插画" />
          <div class="hero-copy">
            <span class="hero-category">{{
              teacher
                ? overview.classes.find((c) => c.id === selected)?.name ||
                  "教学空间"
                : "学习空间"
            }}</span>
            <h2>
              {{
                teacher
                  ? store.data.lesson?.title || "准备下一课"
                  : overview.tasks.find(
                      (t) =>
                        !["已提交", "已反馈", "历史只读"].includes(t.status),
                    )?.title || "我的课程"
              }}
            </h2>
            <RouteButton
              :route="
                teacher
                  ? 'prepare' + (selected ? '?class=' + selected : '')
                  : 'courses'
              "
              >{{ teacher ? "继续备课" : "探索课程" }}</RouteButton
            >
          </div>
        </section>
        <SectionHeading
          :title="teacher ? '当前班级任务' : '我的任务'"
        /><Surface
          ><TaskList :teacher="teacher" :tasks="overview.tasks" /></Surface
        ><Surface v-if="teacher" class="recent-submissions"
          ><SectionHeading title="最近提交" />
          <article
            v-for="item in overview.recentSubmissions"
            :key="item.recordId"
          >
            <strong>{{ item.studentName }}</strong
            ><span>{{ item.taskTitle }}</span
            ><time>{{ deadlineText(item.submittedAt) }}</time
            ><RouteButton :route="'insights?task=' + item.taskId" secondary
              >查看记录</RouteButton
            >
          </article>
          <p v-if="!overview.recentSubmissions.length" class="muted">
            暂无提交
          </p></Surface
        >
      </main>
      <aside>
        <Surface class="dashboard-messages"
          ><SectionHeading
            :title="teacher ? '业务消息' : '新消息与反馈'" /><MessageCenter
            compact /></Surface
        ><Surface class="dashboard-class-entry"
          ><Users :size="24" />
          <h2>{{ teacher ? "班级与成员" : "我的班级" }}</h2>
          <p>{{ overview.classes.length }} 个班级</p>
          <RouteButton route="class" secondary>{{
            teacher ? "管理班级" : "加入或查看班级"
          }}</RouteButton></Surface
        >
      </aside>
    </div></template
  >
</template>
