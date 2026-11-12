<script setup>
import { ref, computed, onMounted, watch, inject, onBeforeUnmount } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useLearning } from "@/store.js";
import { api } from "@/services/api.js";
import { teachingApi, deadlineText } from "@/services/teaching.js";
import TaskList from "@/components/TaskList.vue";
import {
  Plus,
  Users,
  UserPlus,
  Ticket,
  Settings2,
  RefreshCw,
  X,
} from "@/components/app/icons.js";
const store = useLearning(),
  route = useRoute(),
  router = useRouter(),
  notify = inject("notify");
const teacher = computed(() => store.user.role === "teacher"),
  rooms = ref([]),
  members = ref([]),
  tasks = ref([]),
  accounts = ref([]),
  invites = ref([]),
  selected = ref(
    String(
      route.query.class ||
        store.currentClassId ||
        store.data.classroom?.id ||
        "",
    ),
  ),
  student = ref(""),
  error = ref(""),
  busy = ref(false),
  loading = ref(false),
  dialog = ref(""),
  code = ref(""),
  joinCode = ref(""),
  name = ref(""),
  grade = ref(""),
  subject = ref(""),
  inviteDays = ref("7");
let generation = 0;
const view = ref("tasks"), joinOpen = ref(false);
const room = computed(() => rooms.value.find((c) => c.id === selected.value));
const studentRoom = computed(() => rooms.value.find(item => item.id === selected.value) || rooms.value[0]);
const studentTasks = computed(() => (store.data.tasks || []).filter(task => task.classId === studentRoom.value?.id));
async function refreshRooms() {
  rooms.value = await teachingApi.classes();
}
async function load() {
  if (!teacher.value || !selected.value) return;
  const g = ++generation;
  members.value = [];
  tasks.value = [];
  invites.value = [];
  error.value = "";
  loading.value = true;
  store.currentClassId = selected.value;
  store.data.publishClassId = selected.value;
  try {
    const values = await Promise.all([
      api.classroomMembers(selected.value),
      teachingApi.tasks(selected.value),
      teachingApi.invites(selected.value),
    ]);
    if (g !== generation) return;
    [members.value, tasks.value, invites.value] = values;
  } catch (e) {
    if (g === generation) error.value = e.message;
  } finally {
    if (g === generation) loading.value = false;
  }
}
function select() {
  router.replace({ query: { ...route.query, class: selected.value } });
}
onBeforeUnmount(() => {
  generation++;
});
watch(selected, load);
watch(
  () => route.query.class,
  (id) => {
    if (id && id !== selected.value) selected.value = String(id);
  },
);
onMounted(async () => {
  try {
    await refreshRooms();
    if (teacher.value) {
      accounts.value = await api.accounts();
      if (!selected.value) selected.value = rooms.value[0]?.id || "";
      else await load();
    }
  } catch (e) {
    error.value = e.message;
  }
});
function edit(create = false) {
  dialog.value = create ? "create" : "edit";
  name.value = create ? "" : room.value.name;
  grade.value = create ? "" : room.value.grade;
  subject.value = create ? "" : room.value.subject;
}
async function saveClass() {
  busy.value = true;
  error.value = "";
  try {
    const data = {
      name: name.value.trim(),
      grade: grade.value.trim(),
      subject: subject.value.trim(),
    };
    if (dialog.value === "create") {
      const item = await store.createClassroom(data);
      store.data.classrooms.push(item);
      await refreshRooms();
      selected.value = item.id;
    } else {
      await teachingApi.editClass(selected.value, data);
      await refreshRooms();
    }
    dialog.value = "";
    notify("班级已保存");
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
async function add() {
  busy.value = true;
  try {
    await store.addMember(selected.value, student.value);
    student.value = "";
    await load();
    await refreshRooms();
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
async function remove(item) {
  if (
    !confirm("移出后停止新任务分配，保留该学生历史作答；本人历史只读。继续？")
  )
    return;
  try {
    await teachingApi.removeMember(selected.value, item.id);
    await load();
    await refreshRooms();
  } catch (e) {
    error.value = e.message;
  }
}
async function createInvite() {
  try {
    const result = await teachingApi.invite(
      selected.value,
      Number(inviteDays.value),
    );
    code.value = result.code;
    await load();
  } catch (e) {
    error.value = e.message;
  }
}
async function revoke(item) {
  try {
    await teachingApi.revoke(selected.value, item.id);
    await load();
  } catch (e) {
    error.value = e.message;
  }
}
async function backfill(task) {
  if (!members.value.length) return;
  if (
    !confirm(
      "将此历史任务的原始快照补发给当前班级尚未分配的学生？已分配记录保持不变。",
    )
  )
    return;
  try {
    const result = await teachingApi.assign(
      task.id,
      members.value.map((m) => m.id),
    );
    notify("已补发给" + result.created + "名学生");
    await load();
  } catch (e) {
    error.value = e.message;
  }
}
async function join() {
  busy.value = true;
  error.value = "";
  try {
    const result = await teachingApi.join(joinCode.value.trim());
    joinCode.value = "";
    await refreshRooms();
    await store.load(store.data.lesson?.id, true);
    joinOpen.value=false;
    notify(result.created ? "已加入班级" : "你已在该班级中");
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
</script>
<template>
  <PageHeading :title="teacher ? '班级教学' : '我的班级'">
    <AppButton v-if="teacher" variant="outline" @click="edit(true)"><Plus :size="16"/>新建班级</AppButton>
    <RouteButton v-if="teacher && room" :route="'prepare?class='+selected">发布学习任务</RouteButton>
    <AppButton v-if="!teacher" @click="joinOpen=true"><Plus :size="16"/>加入班级</AppButton>
  </PageHeading>
  <AppAlert type="error" v-if="error" class="form-error" role="alert">{{error}}</AppAlert>
  <template v-if="teacher">
    <div class="teaching-class-toolbar ops-context-row">
      <AppSelect v-model="selected" label="当前班级" @update:model-value="select" :options="rooms.map(r=>({value:r.id,label:r.name}))"/>
      <span v-if="room">{{room.grade}} 　 {{room.subject}} 　 {{members.length}} 人</span>
      <AppButton variant="ghost" size="icon-sm" aria-label="刷新班级" @click="load"><RefreshCw :size="16"/></AppButton>
      <AppButton v-if="room" variant="ghost" @click="edit(false)"><Settings2 :size="16"/>班级设置</AppButton>
    </div>
    <template v-if="room">
      <AppTabs v-model="view" :items="[{value:'tasks',label:'学习任务'},{value:'members',label:'成员与邀请'}]"/>
      <section v-if="view==='tasks'" class="ops-section">
        <p v-if="loading" role="status">读取任务…</p>
        <Surface v-else class="teaching-tasks"><TaskList teacher :tasks="tasks"/></Surface>
        <details v-if="tasks.length" class="ops-disclosure"><summary>补发历史任务</summary>
          <div v-for="task in tasks" :key="task.id" class="task-allocation"><span><strong>{{task.title}}</strong><small>{{task.summary.assigned}} 人已分配 　 {{task.summary.inactive}} 人历史保留</small></span><AppButton variant="outline" @click="backfill(task)">补发给当前成员</AppButton></div>
        </details>
      </section>
      <div v-else class="ops-member-layout">
        <Surface class="teaching-members"><header><h2>班级成员</h2><span>{{members.length}} 人</span></header>
          <div class="ops-add-member"><AppSelect v-model="student" label="添加已有学生" :options="accounts.filter(a=>!members.some(m=>m.id===a.id)).map(a=>({value:a.id,label:a.displayName+' 　 '+a.username}))"/><AppButton :disabled="busy||!student||loading" @click="add"><UserPlus :size="15"/>添加</AppButton></div>
          <p v-if="loading" role="status">读取成员…</p><AppEmpty v-else-if="!members.length" class="empty-state">暂无班级成员</AppEmpty>
          <div v-for="item in members" :key="item.id" class="teaching-member"><span class="avatar">{{item.displayName.slice(0,1)}}</span><div><strong>{{item.displayName}}</strong><p>{{item.username}}</p></div><AppButton variant="ghost" size="icon-sm" :aria-label="'移出'+item.displayName" @click="remove(item)"><X :size="14"/></AppButton></div>
        </Surface>
        <Surface class="teaching-invites"><header><h2>邀请学生</h2><Ticket :size="17"/></header><label class="field-label">邀请码有效期<AppSelect v-model="inviteDays" label="邀请码有效期" :options="[{value:'1',label:'1天'},{value:'7',label:'7天'},{value:'30',label:'30天'}]"/></label><AppButton variant="outline" @click="createInvite">生成邀请码</AppButton><p v-if="code" class="invitation-code" aria-label="新邀请码">{{code}}</p>
          <details v-if="invites.length" class="ops-disclosure"><summary>已生成的邀请码</summary><div v-for="item in invites" :key="item.id"><Status>{{item.revoked?'已撤销':item.expired?'已过期':'有效'}}</Status><time>{{deadlineText(item.expiresAt)}}</time><AppButton v-if="!item.revoked&&!item.expired" variant="ghost" @click="revoke(item)">撤销</AppButton></div></details>
        </Surface>
      </div>
    </template>
    <Surface v-else><AppEmpty class="empty-state"><Users :size="28"/><h2>还没有班级</h2><AppButton @click="edit(true)">新建班级</AppButton></AppEmpty></Surface>
  </template>
  <template v-else>
    <div v-if="rooms.length" class="student-class-workbench">
      <nav class="student-class-picker" aria-label="我的班级">
        <button v-for="item in rooms" :key="item.id" :aria-current="studentRoom?.id===item.id?'true':undefined" @click="selected=item.id;select()">
          <Users :size="20"/>
          <span><strong>{{item.name}}</strong><span class="class-meta"><span>{{item.grade}}</span><span>{{item.subject}}</span><span v-if="item.teacherName">{{item.teacherName.replaceAll('\u00b7',' ')}}</span></span></span>
        </button>
      </nav>
      <Surface class="student-class-tasks">
        <header class="section-heading"><h2>{{studentRoom.name}}</h2><span>{{studentTasks.length}} 项任务</span></header>
        <TaskList :tasks="studentTasks" empty-label="老师还没有布置任务"/>
        <RouteButton v-if="!studentTasks.length" route="courses" secondary>浏览课程</RouteButton>
      </Surface>
    </div>
    <Surface v-else><AppEmpty class="empty-state"><Users :size="28"/><h2>还没有加入班级</h2><AppButton @click="joinOpen=true">输入邀请码</AppButton></AppEmpty></Surface>
  </template>
  <AppDialog v-model:open="joinOpen" title="加入班级"><form class="class-edit-form" @submit.prevent="join"><label class="field-label">班级邀请码<Input v-model="joinCode" autocomplete="off" required/></label><AppAlert type="error" v-if="error" class="form-error" role="alert">{{error}}</AppAlert><AppButton :disabled="busy||!joinCode.trim()">加入班级</AppButton></form></AppDialog>
  <AppDialog
    :open="!!dialog"
    :title="dialog === 'create' ? '新建班级' : '编辑班级'"
    @update:open="
      (value) => {
        if (!value) dialog = '';
      }
    "
    ><form class="class-edit-form" @submit.prevent="saveClass">
      <label class="field-label"
        >班级名称<Input v-model="name" required /></label
      ><label class="field-label"
        >年级<Input v-model="grade" required placeholder="例如七年级" /></label
      ><label class="field-label"
        >学科<Input v-model="subject" required
      /></label>
      <AppAlert type="error" v-if="error" class="form-error">{{ error }}</AppAlert>
      <AppButton
        type="submit"
        :disabled="busy || !name.trim() || !grade.trim() || !subject.trim()"
        >保存班级</AppButton
      >
    </form></AppDialog
  >
</template>
