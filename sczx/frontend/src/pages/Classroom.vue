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
} from "lucide-vue-next";
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
const room = computed(() => rooms.value.find((c) => c.id === selected.value));
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
    notify(result.created ? "已加入班级" : "你已在该班级中");
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
</script>
<template>
  <PageHeading :title="teacher ? room?.name || '班级教学' : '我的班级'"
    ><template v-if="teacher"
      ><Button variant="outline" @click="edit(true)"
        ><Plus :size="16" />新建班级</Button
      ><Button v-if="room" variant="outline" @click="edit(false)"
        ><Settings2 :size="16" />编辑班级</Button
      ><RouteButton v-if="room" :route="'prepare?class=' + selected"
        >备课并发布</RouteButton
      ></template
    ></PageHeading
  >
  <p v-if="error" class="form-error" role="alert">{{ error }}</p>
  <template v-if="teacher"
    ><div class="teaching-class-toolbar">
      <AppSelect
        v-model="selected"
        label="当前班级"
        @update:model-value="select"
        :options="rooms.map((r) => ({ value: r.id, label: r.name }))"
      /><span v-if="room"
        >{{ room.grade }} · {{ room.subject }} · {{ members.length }} 人</span
      ><Button
        variant="ghost"
        size="icon-sm"
        aria-label="刷新当前班级"
        @click="load"
        ><RefreshCw :size="16"
      /></Button>
    </div>
    <div v-if="room" class="teaching-class-grid">
      <aside>
        <Surface class="teaching-members"
          ><header>
            <h2>班级成员</h2>
            <Users :size="17" />
          </header>
          <AppSelect
            v-model="student"
            label="添加已有学生"
            :options="
              accounts
                .filter((a) => !members.some((m) => m.id === a.id))
                .map((a) => ({
                  value: a.id,
                  label: a.displayName + ' · ' + a.username,
                }))
            " /><Button
            variant="outline"
            :disabled="busy || !student || loading"
            @click="add"
            ><UserPlus :size="15" />添加学生</Button
          >
          <p v-if="loading" role="status">读取中…</p>
          <div v-for="item in members" :key="item.id" class="teaching-member">
            <span class="avatar">{{ item.displayName.slice(0, 1) }}</span>
            <div>
              <strong>{{ item.displayName }}</strong>
              <p>
                {{
                  item.classes?.map((c) => c.name).join(" / ") || item.username
                }}
              </p>
            </div>
            <Button
              variant="ghost"
              size="icon-sm"
              :aria-label="'移出' + item.displayName"
              @click="remove(item)"
              ><X :size="14"
            /></Button></div></Surface
        ><Surface class="teaching-invites"
          ><header>
            <h2>班级邀请</h2>
            <Ticket :size="17" />
          </header>
          <label class="field-label"
            >有效期<AppSelect
              v-model="inviteDays"
              label="邀请码有效期"
              :options="[
                { value: '1', label: '1天' },
                { value: '7', label: '7天' },
                { value: '30', label: '30天' },
              ]" /></label
          ><Button variant="outline" @click="createInvite">生成邀请码</Button>
          <p v-if="code" class="invitation-code" aria-label="新邀请码">
            {{ code }}
          </p>
          <div v-for="item in invites" :key="item.id">
            <Status>{{
              item.revoked ? "已撤销" : item.expired ? "已过期" : "有效"
            }}</Status
            ><time>{{ deadlineText(item.expiresAt) }}</time
            ><Button
              v-if="!item.revoked && !item.expired"
              variant="ghost"
              @click="revoke(item)"
              >撤销</Button
            >
          </div></Surface
        >
      </aside>
      <Surface class="teaching-tasks"
        ><SectionHeading title="班级任务" />
        <p v-if="loading" role="status">读取中…</p>
        <TaskList v-else teacher :tasks="tasks" />
        <div v-for="task in tasks" :key="task.id" class="task-allocation">
          <span
            >{{ task.title }} · {{ task.summary.assigned }} 人已分配 ·
            {{ task.summary.inactive }} 人历史保留</span
          ><Button variant="ghost" @click="backfill(task)"
            >补发给当前成员</Button
          >
        </div></Surface
      >
    </div>
    <Surface v-else
      ><div class="empty-state">
        <h2>创建第一个班级</h2>
        <Button @click="edit(true)">新建班级</Button>
      </div></Surface
    ></template
  >
  <template v-else
    ><div class="student-class-grid">
      <Surface class="student-join"
        ><h2>加入班级</h2>
        <form @submit.prevent="join">
          <label class="field-label"
            >班级邀请码<Input
              v-model="joinCode"
              autocomplete="off"
              required /></label
          ><Button type="submit" :disabled="busy || !joinCode.trim()"
            >加入班级</Button
          >
        </form></Surface
      ><Surface v-for="item in rooms" :key="item.id" class="student-class"
        ><Users :size="24" />
        <h2>{{ item.name }}</h2>
        <p>{{ item.grade }} · {{ item.subject }}</p>
        <p>{{ item.teacherName }}</p>
        <RouteButton route="home" secondary
          >查看已分配任务</RouteButton
        ></Surface
      >
    </div></template
  >
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
      <p v-if="error" class="form-error">{{ error }}</p>
      <Button
        type="submit"
        :disabled="busy || !name.trim() || !grade.trim() || !subject.trim()"
        >保存班级</Button
      >
    </form></AppDialog
  >
</template>
