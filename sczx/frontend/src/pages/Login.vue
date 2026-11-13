<script setup>
import { ref, watch } from "vue";
import { ElForm, ElFormItem, ElInput, ElSelect, ElOption, ElButton, ElImage, ElAside, ElContainer } from "element-plus";
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
const errorField = ref("password");
watch([username, password, displayName, role, mode], () => { error.value = ""; });
const busy = ref(false);

async function submit() {
  if (busy.value) return;
  if (!username.value.trim() || !password.value) {
    errorField.value = !username.value.trim() ? "username" : "password";
    error.value = !username.value.trim() ? "请填写账号或学号。" : "请填写密码。";
    return;
  }
  if (mode.value === "register" && password.value.length < 6) {
    errorField.value = "password";
    error.value = "密码至少6位。";
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
    errorField.value = problem.status === 409 ? "username" : "password";
    error.value = problem.message;
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <ElContainer class="login-screen login-refined">
    <ElAside class="auth-art" width="48%" aria-label="学习平台插画"><ElImage class="auth-illustration" src="/images/auth/pure-admin-illustration.svg" fit="contain" alt="学习与协作插画"/></ElAside>
    <ElMain class="auth-form-panel">
    <Surface class="login-card" aria-labelledby="login-title">
      <div class="login-brand"><ElAvatar shape="square" :size="40" class="brand-symbol"><BookOpenText :size="25" /></ElAvatar><span>师承智学</span></div>
      <h1 id="login-title">{{ mode === 'login' ? '账号登录' : '创建账号' }}</h1>
      <AppTabs v-model="mode" :items="[{value:'login',label:'登录'},{value:'register',label:'注册'}]" @update:model-value="error=''"/>
      <ElForm label-position="top" size="large" :inline-message="true" @submit.prevent="submit">
        <template v-if="mode==='register'">
          <ElFormItem label="身份" for="register-role"><ElSelect id="register-role" v-model="role" aria-label="注册身份" :disabled="busy"><ElOption label="学生" value="student"/><ElOption label="教师" value="teacher"/></ElSelect></ElFormItem>
          <ElFormItem label="姓名" for="register-name"><ElInput id="register-name" v-model="displayName" required maxlength="120" autocomplete="name" placeholder="输入姓名" :disabled="busy"/></ElFormItem>
        </template>
        <ElFormItem :label="mode==='register' && role==='student'?'学号':'账号 / 学号'" for="login-username" :error="errorField==='username'?error:''"><ElInput id="login-username" v-model="username" autocomplete="username" :placeholder="mode==='register' && role==='student'?'输入学号':'输入账号或学号'" :disabled="busy" required/></ElFormItem>
        <ElFormItem label="密码" for="login-password" :error="errorField==='password'?error:''"><ElInput id="login-password" v-model="password" type="password" show-password :autocomplete="mode==='register'?'new-password':'current-password'" :minlength="mode==='register'?6:undefined" :placeholder="mode==='register'?'设置密码（至少6位）':'输入密码'" :disabled="busy" required/></ElFormItem>
        <ElButton class="login-submit" type="primary" size="large" native-type="submit" :loading="busy" :disabled="busy">{{ mode==='register'?"注册并进入":"登录" }}<ArrowRight :size="17" /></ElButton>
      </ElForm>
    </Surface>
    </ElMain>
  </ElContainer>
</template>

<style scoped>
.login-screen.login-refined { display:flex; flex-direction:row; align-items:stretch; justify-content:flex-start; height:100dvh; min-height:0; box-sizing:border-box; padding:0; overflow:hidden; background:var(--el-bg-color); --el-transition-duration:0s; --el-transition-duration-fast:0s; }
.login-refined .auth-art { display:flex; align-items:center; justify-content:center; padding:40px 28px 40px clamp(32px,4vw,64px); background:var(--el-color-primary-light-9); border-right:1px solid var(--el-border-color-lighter); }
.login-refined .auth-illustration { display:block; width:100%; max-width:none; height:78vh; }
.login-refined .auth-illustration :deep(.el-image__inner) { object-position:right center; }
.login-refined .auth-form-panel { display:flex; flex-direction:column; align-items:flex-start; padding:clamp(36px,10vh,100px) clamp(32px,4vw,64px) 32px; overflow-y:auto; scrollbar-gutter:stable both-edges; }
.login-refined .login-card.el-card { width:min(480px,100%); flex-shrink:0; align-self:flex-start; margin:0; --el-card-border-color:transparent; --el-card-bg-color:transparent; border-radius:0; box-shadow:none; }
.login-refined .login-card.el-card :deep(>.el-card__body) { padding:0; }
.login-refined .login-brand { gap:12px; margin:0 0 24px; font-size:19px; }
.login-refined .brand-symbol.el-avatar { width:40px; height:40px; background:var(--el-color-primary); color:var(--el-color-white); border-radius:var(--el-border-radius-base); }
.login-refined h1 { margin:0 0 18px; font-size:24px; line-height:1.4; }
.login-refined :deep(.el-tabs__header) { margin-bottom:20px; }
.login-refined :deep(.el-tabs__active-bar),.login-refined :deep(.el-form-item__error) { transition:none; animation:none; }
.login-refined .el-form { --el-component-size-large:44px; gap:0; }
.login-refined .el-form-item { margin:0 0 18px; }
.login-refined :deep(.el-form-item__label) { padding:0; margin-bottom:8px; line-height:20px; font-size:14px; }
.login-refined :deep(.el-input__wrapper),.login-refined :deep(.el-select__wrapper) { height:44px; min-height:44px; box-sizing:border-box; }
.login-refined :deep(.el-input__inner) { height:42px; font-size:14px; }
.login-refined .login-submit.el-button { height:44px; min-height:44px; margin:6px 0 0; width:100%; justify-content:center; border-radius:var(--el-border-radius-base); background:var(--el-color-primary); }
.login-refined .login-submit :deep(>span) { display:flex; align-items:center; justify-content:center; gap:10px; }
.login-refined :deep(.el-form-item__error--inline) { margin:6px 0 0; width:100%; line-height:1.5; }
@media(max-width:1000px) { .login-refined .auth-art { width:44%; padding:24px; }.login-refined .auth-form-panel { padding:40px 20px; } }
@media(max-width:700px) { .login-refined .auth-art { display:none; }.login-refined .auth-form-panel { padding:28px 12px; }.login-refined .login-card.el-card :deep(>.el-card__body) { padding:0; } }
</style>
