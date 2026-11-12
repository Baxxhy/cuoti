<script setup>
import { ref } from "vue";
import { useRouter, useRoute } from "vue-router";
import { BookOpenText, ArrowRight, Eye, EyeOff } from "@/components/app/icons.js";
import { useLearning } from "@/store.js";

const store = useLearning();
const router = useRouter();
const route = useRoute();
const username = ref("");
const password = ref("");
const showPassword=ref(false);
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
  <main class="login-screen login-refined">
    <section class="login-card" aria-labelledby="login-title">
      <div class="login-brand"><span class="brand-symbol"><BookOpenText :size="25" /></span><span>师承智学</span></div>
      <h1 id="login-title">账号登录</h1>
      <form @submit.prevent="submit">
        <div class="login-field"><label for="login-username">账号</label><Input id="login-username" v-model="username" autocomplete="username" placeholder="输入账号" :disabled="busy" required /></div>
        <div class="login-field"><label for="login-password">密码</label><div class="login-password"><Input id="login-password" v-model="password" :type="showPassword?'text':'password'" autocomplete="current-password" placeholder="输入密码" :disabled="busy" required /><button type="button" :aria-label="showPassword?'隐藏密码':'显示密码'" :aria-pressed="showPassword" @click="showPassword=!showPassword"><EyeOff v-if="showPassword" :size="18"/><Eye v-else :size="18"/></button></div></div>
        <AppAlert type="error" v-if="error" class="form-error" role="alert">{{ error }}</AppAlert>
        <AppButton class="login-submit" type="submit" :disabled="busy">{{ busy ? "正在登录…" : "登录" }}<ArrowRight :size="18" /></AppButton>
      </form>
    </section>
  </main>
</template>
