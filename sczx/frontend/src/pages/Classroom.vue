<script setup>
import { computed, ref, inject, onMounted, watch } from "vue";
import { Users, Plus, UserPlus } from "lucide-vue-next";
import TaskList from "@/components/TaskList.vue";
import { api } from "@/services/api.js";
import { useLearning } from "@/store.js";
const store = useLearning();
const notify = inject("notify");
const accounts = ref([]);
const members = ref([]);
const selectedClassId = ref(store.data.classroom?.id || "");
const selectedStudentId = ref("");
const className = ref("");
const error = ref("");
const busy = ref(false);
const classroom = computed(() => store.data.classrooms?.find((c) => c.id === selectedClassId.value) || store.data.classroom);
async function loadAccounts() {
  try { accounts.value = await api.accounts(); }
  catch (problem) { error.value = problem.message; }
}
async function loadMembers() {
  if (!selectedClassId.value) { members.value = []; return; }
  try { members.value = await api.classroomMembers(selectedClassId.value); }
  catch (problem) { error.value = problem.message; }
}
async function createClass() {
  if (busy.value || !className.value.trim()) return;
  busy.value = true; error.value = "";
  try {
    const item = await store.createClassroom({ name: className.value.trim(), grade: "七年级数学" });
    store.data.classrooms = [...(store.data.classrooms || []), item];
    selectedClassId.value = item.id;
    store.data.classroom = item;
    members.value = [];
    className.value = "";
    notify("班级已创建");
  } catch (problem) { error.value = problem.message; }
  finally { busy.value = false; }
}
async function addStudent() {
  if (busy.value || !selectedClassId.value || !selectedStudentId.value) return;
  busy.value = true; error.value = "";
  try {
    await store.addMember(selectedClassId.value, selectedStudentId.value);
    await loadMembers();
    if (selectedClassId.value === store.data.classroom?.id) await store.load();
    selectedStudentId.value = "";
    notify("学生已加入班级");
  } catch (problem) { error.value = problem.message; }
  finally { busy.value = false; }
}
watch(selectedClassId, () => loadMembers());
onMounted(loadAccounts);
</script>

<template>
  <PageHeading :title="classroom?.name || '班级教学'"><RouteButton route="prepare">发布新任务</RouteButton></PageHeading>
  <p v-if="error" role="alert" class="form-error">{{ error }}</p>
  <div class="class-banner">
    <div class="class-mark"><Users :size="35" /></div>
    <div><p>{{ classroom?.grade || "七年级数学" }} · {{ members.length }} 名学生</p></div>
    <div class="student-avatars"><span v-for="member in members" :key="member.id" :title="member.displayName">{{ member.displayName.slice(0,1) }}</span></div>
  </div>
  <div class="class-admin-grid">
    <Surface>
      <SectionHeading title="班级" />
      <label class="field-label" for="class-select">当前班级</label>
      <select id="class-select" v-model="selectedClassId" @change="store.data.publishClassId = selectedClassId"><option v-for="item in store.data.classrooms" :key="item.id" :value="item.id">{{ item.name }}</option></select>
      <form class="class-create" @submit.prevent="createClass"><label class="field-label" for="new-class">新建班级</label><Input id="new-class" v-model="className" placeholder="班级名称" required /><Button type="submit" :disabled="busy"><Plus :size="16" />创建班级</Button></form>
    </Surface>
    <Surface>
      <SectionHeading title="添加学生" />
      <label class="field-label" for="class-student">学生账号</label>
      <select id="class-student" v-model="selectedStudentId"><option value="">选择学生账号</option><option v-for="account in accounts" :key="account.id" :value="account.id">{{ account.displayName }} · {{ account.username }}</option></select>
      <Button class="member-add" :disabled="busy || !selectedStudentId || !selectedClassId" @click="addStudent"><UserPlus :size="16" />加入当前班级</Button>
      <div class="member-list"><div v-for="member in members" :key="member.id"><span class="avatar">{{ member.displayName.slice(0,1) }}</span><strong>{{ member.displayName }}</strong><span>{{ member.username }}</span></div><p v-if="!members.length" class="muted">班级还没有学生</p></div>
    </Surface>
  </div>
  <SectionHeading title="班级学习任务" /><Surface><TaskList teacher /></Surface>
</template>
