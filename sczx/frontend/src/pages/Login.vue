<script setup>
import { ref } from "vue";
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
    <Surface data-ui="card" class="login-card" aria-labelledby="login-title">
      <div class="login-brand"><ElAvatar shape="square" :size="36" class="brand-symbol"><BookOpenText :size="25" /></ElAvatar><span>师承智学</span></div>
      <h1 id="login-title">{{ mode === 'login' ? '账号登录' : '创建账号' }}</h1>
      <AppTabs v-model="mode" :items="[{value:'login',label:'登录'},{value:'register',label:'注册'}]" @update:model-value="error=''"/>
      <ElForm @submit.prevent="submit">
        <template v-if="mode==='register'"><div class="login-field"><label>身份</label><AppSelect v-model="role" label="注册身份" :options="[{value:'student',label:'学生'},{value:'teacher',label:'教师'}]"/></div><div class="login-field"><label for="register-name">姓名</label><Input id="register-name" v-model="displayName" required maxlength="120" autocomplete="name"/></div></template>
        <div class="login-field"><label for="login-username">{{mode==='register' && role==='student'?'学号（用于登录）':'账号 / 学号'}}</label><Input id="login-username" v-model="username" autocomplete="username" placeholder="输入账号" :disabled="busy" required /></div>
        <div class="login-field"><label for="login-password">密码</label><div class="login-password"><Input id="login-password" v-model="password" type="password" show-password :autocomplete="mode==='register'?'new-password':'current-password'" :minlength="mode==='register'?3:undefined" placeholder="输入密码" :disabled="busy" required /></div></div>
        <AppAlert type="error" v-if="error" class="form-error" role="alert">{{ error }}</AppAlert>
        <AppButton class="login-submit" type="submit" :disabled="busy">{{ busy ? "请稍候…" : mode==='register'?"注册并进入":"登录" }}<ArrowRight :size="18" /></AppButton>
      </ElForm>
    </Surface>
  </ElMain>
</template>
