<script setup>
import { onMounted, ref, inject } from "vue";
import { api } from "@/services/api.js";
const notify = inject("notify");
const accounts = ref([]);
const busy = ref(false), createOpen = ref(false);
const error = ref("");
const form = ref({ username: "", displayName: "", role: "teacher", password: "" });
async function load() {
  error.value = "";
  try { accounts.value = await api.accounts(); }
  catch (problem) { error.value = problem.message; }
}
async function create() {
  if (busy.value) return;
  busy.value = true;
  error.value = "";
  try {
    await api.createAccount(form.value);
    form.value = { username: "", displayName: "", role: "teacher", password: "" };
    await load();
    createOpen.value = false;
    notify("账号已创建");
  } catch (problem) { error.value = problem.message; }
  finally { busy.value = false; }
}
onMounted(load);
</script>

<template>
  <section class="account-manager">
    <SectionHeading title="账号管理"><Button @click="createOpen=true">新建账号</Button></SectionHeading>
    <p v-if="error" role="alert" class="form-error">{{ error }}</p>
    <AppDialog v-model:open="createOpen" title="新建账号"><form class="account-form" @submit.prevent="create">
      <label class="field-label" for="account-username">登录账号</label><Input id="account-username" v-model="form.username" autocomplete="off" required minlength="2" />
      <label class="field-label" for="account-name">显示名称</label><Input id="account-name" v-model="form.displayName" required />
      <label class="field-label" for="account-role">身份</label><select id="account-role" v-model="form.role"><option value="teacher">教师</option><option value="student">学生</option></select>
      <label class="field-label" for="account-password">初始密码</label><Input id="account-password" v-model="form.password" type="password" autocomplete="new-password" required minlength="8" />
      <Button type="submit" :disabled="busy">{{ busy ? "创建中…" : "创建账号" }}</Button>
      <p v-if="error" role="alert" class="form-error">{{error}}</p>
    </form></AppDialog>
    <div class="account-list admin-account-table" aria-label="已有账号"><div class="admin-account-header"><span>名称</span><span>账号</span><span>身份</span></div>
      <div v-for="account in accounts" :key="account.id" class="account-row"><div><span class="avatar">{{ account.displayName.slice(0,1) }}</span><strong>{{ account.displayName }}</strong></div><span>{{ account.username }}</span><span>{{ account.role === "teacher" ? "教师" : account.role === "student" ? "学生" : "管理员" }}</span></div>
      <p v-if="!accounts.length" class="muted">暂无账号</p>
    </div>
  </section>
</template>
