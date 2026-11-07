<script setup>
import { ref } from "vue";
import { useRouter, useRoute } from "vue-router";
import { BookOpenText, ArrowRight } from "lucide-vue-next";
import { useLearning } from "@/store.js";

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
  <main class="login-screen">
    <section class="login-card" aria-labelledby="login-title">
      <div class="login-brand"><span class="brand-symbol"><BookOpenText :size="24" /></span><span>师承智学</span></div>
      <h1 id="login-title">登录</h1>
      <form @submit.prevent="submit">
        <label class="field-label" for="login-username">账号</label>
        <Input id="login-username" v-model="username" autocomplete="username" required />
        <label class="field-label" for="login-password">密码</label>
        <Input id="login-password" v-model="password" type="password" autocomplete="current-password" required />
        <p v-if="error" class="form-error" role="alert">{{ error }}</p>
        <Button class="login-submit" type="submit" :disabled="busy">{{ busy ? "正在登录…" : "进入学习平台" }}<ArrowRight :size="17" /></Button>
      </form>
    </section>
  </main>
</template>
