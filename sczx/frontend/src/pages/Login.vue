<script setup>
import { ref } from "vue";
import { ElForm, ElFormItem, ElInput, ElSelect, ElOption, ElButton } from "element-plus";
import { useRouter, useRoute } from "vue-router";
import { BookOpenText, ArrowRight } from "@/components/app/icons.js";
import { useLearning } from "@/store.js";

import { api } from "@/services/api.js";
const mode = ref("login"), role = ref("student"), displayName = ref("");
const store = useLearning();
const router = useRouter();
const route = useRoute();
const username = ref("");
const password = ref("");
const error = ref("");
const busy = ref(false);

async function submit() {
  if (busy.value) return;
  if (!username.value.trim() || !password.value) {
    error.value = "请填写账号和密码。";
    return;
  }
  busy.value = true;
  error.value = "";
  try {
    if (mode.value === "register") {
      await api.register({ username: username.value.trim(), password: password.value, displayName: displayName.value.trim(), role: role.value });
    }
    await store.login(username.value.trim(), password.value);
    const fallback = store.user.role === "teacher" ? "/teacher" : store.user.role === "admin" ? "/manage" : "/home";
    await router.replace(typeof route.query.next === "string" ? route.query.next : fallback);
  } catch (problem) {
    error.value = problem.message;
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <ElMain class="login-screen login-refined">
    <Surface class="login-card" aria-labelledby="login-title">
      <div class="login-brand"><ElAvatar shape="square" :size="40" class="brand-symbol"><BookOpenText :size="25" /></ElAvatar><span>师承智学</span></div>
      <h1 id="login-title">{{ mode === 'login' ? '账号登录' : '创建账号' }}</h1>
      <AppTabs v-model="mode" :items="[{value:'login',label:'登录'},{value:'register',label:'注册'}]" @update:model-value="error=''"/>
      <ElForm label-position="top" size="large" @submit.prevent="submit">
        <template v-if="mode==='register'">
          <ElFormItem label="身份" for="register-role"><ElSelect id="register-role" v-model="role" aria-label="注册身份" :disabled="busy"><ElOption label="学生" value="student"/><ElOption label="教师" value="teacher"/></ElSelect></ElFormItem>
          <ElFormItem label="姓名" for="register-name"><ElInput id="register-name" v-model="displayName" required maxlength="120" autocomplete="name" placeholder="输入姓名" :disabled="busy"/></ElFormItem>
        </template>
        <ElFormItem :label="mode==='register' && role==='student'?'学号':'账号 / 学号'" for="login-username"><ElInput id="login-username" v-model="username" autocomplete="username" :placeholder="mode==='register' && role==='student'?'输入学号':'输入账号或学号'" :disabled="busy" required/></ElFormItem>
        <ElFormItem label="密码" for="login-password"><ElInput id="login-password" v-model="password" type="password" show-password :autocomplete="mode==='register'?'new-password':'current-password'" :minlength="mode==='register'?6:undefined" :placeholder="mode==='register'?'设置密码（至少6位）':'输入密码'" :disabled="busy" required/></ElFormItem>
        <AppAlert type="error" v-if="error" class="form-error" role="alert">{{ error }}</AppAlert>
        <ElButton class="login-submit" type="primary" size="large" native-type="submit" :loading="busy" :disabled="busy">{{ mode==='register'?"注册并进入":"登录" }}<ArrowRight :size="17" /></ElButton>
      </ElForm>
    </Surface>
  </ElMain>
</template>

<style scoped>
.login-screen.login-refined { padding:32px 24px; }
.login-refined .login-card.el-card { width:min(420px,100%); border-radius:var(--el-border-radius-round); box-shadow:var(--el-box-shadow-light); }
.login-refined .login-card.el-card :deep(>.el-card__body) { padding:32px; }
.login-refined .login-brand { gap:12px; margin:0 0 24px; font-size:19px; }
.login-refined .brand-symbol.el-avatar { width:40px; height:40px; background:var(--el-color-primary); color:var(--el-color-white); border-radius:var(--el-border-radius-base); }
.login-refined h1 { margin:0 0 18px; font-size:24px; line-height:1.4; }
.login-refined :deep(.el-tabs__header) { margin-bottom:20px; }
.login-refined .el-form { --el-component-size-large:44px; gap:0; }
.login-refined .el-form-item { margin:0 0 18px; }
.login-refined :deep(.el-form-item__label) { padding:0; margin-bottom:8px; line-height:20px; font-size:14px; }
.login-refined :deep(.el-input__wrapper),.login-refined :deep(.el-select__wrapper) { height:44px; min-height:44px; box-sizing:border-box; }
.login-refined :deep(.el-input__inner) { height:42px; font-size:14px; }
.login-refined .login-submit.el-button { height:44px; min-height:44px; margin:6px 0 0; width:100%; justify-content:center; border-radius:var(--el-border-radius-base); background:var(--el-color-primary); }
.login-refined .login-submit :deep(>span) { display:flex; align-items:center; justify-content:center; gap:10px; }
.login-refined .form-error { margin-bottom:12px; }
@media(max-width:480px) { .login-screen.login-refined { padding:20px 16px; }.login-refined .login-card.el-card :deep(>.el-card__body) { padding:26px; } }
</style>
