<template>
  <view class="auth-shell">
    <view class="auth-page">
      <view class="auth-top">
        <view class="auth-brand">
          <uni-icons aria-hidden="true" type="compose" size="25" color="var(--color-primary)" />
          <text>错题帮</text>
        </view>
        <!-- #ifdef H5 -->
        <component :is="'h1'" class="auth-title">登录账号</component>
        <!-- #endif -->
        <!-- #ifndef H5 -->
        <text class="auth-title">登录账号</text>
        <!-- #endif -->
      </view>
      <view class="auth-form">
        <account-field
          id="login-email"
          v-model="email"
          label="邮箱"
          inputmode="email"
          autocomplete="username"
          placeholder="请输入邮箱"
          :described-by="notice ? 'login-notice' : undefined"
        />
        <account-field
          id="login-password"
          v-model="password"
          label="密码"
          type="password"
          autocomplete="current-password"
          placeholder="请输入密码"
          :described-by="notice ? 'login-notice' : undefined"
          @confirm="submit"
        />
        <text v-if="notice" id="login-notice" class="account-notice" role="alert">
          {{ notice }}
        </text>
        <button
          class="primary-btn"
          role="button"
          tabindex="0"
          @keydown.enter.prevent="submit"
          @keydown.space.prevent
          @keyup.space.prevent="submit"
          :disabled="!canSubmit || busy"
          @click="submit"
        >
          {{ busy ? '正在登录…' : '登录' }}
        </button>
        <view class="auth-links">
          <button
            role="button"
            tabindex="0"
            @click="go('/pages/register/register')"
            @keydown.enter.prevent="go('/pages/register/register')"
            @keydown.space.prevent
            @keyup.space.prevent="go('/pages/register/register')"
          >
            注册账号
          </button>
          <button
            class="auth-password-link"
            role="button"
            tabindex="0"
            @click="go('/pages/forgot/forgot')"
            @keydown.enter.prevent="go('/pages/forgot/forgot')"
            @keydown.space.prevent
            @keyup.space.prevent="go('/pages/forgot/forgot')"
          >
            修改密码
          </button>
        </view>
      </view>
    </view>
  </view>
</template>
<script setup>
import { computed, onMounted, ref } from 'vue'
import { roleHome, useAppStore } from '@/store/index.js'
import { go } from '@/utils/navigation.js'
import AccountField from '@/components/account-field/account-field.vue'
const email = ref(''),
  password = ref(''),
  busy = ref(false),
  notice = ref(''),
  store = useAppStore()
const canSubmit = computed(() => !!email.value && !!password.value)
async function restore() {
  const user = await store.restoreSession()
  if (user) uni.reLaunch({ url: roleHome(user.role) })
}
async function submit() {
  if (!canSubmit.value || busy.value) return
  busy.value = true
  notice.value = ''
  try {
    const user = await store.login(email.value.trim(), password.value)
    uni.reLaunch({ url: roleHome(user.role) })
  } catch (err) {
    notice.value = err.message || '暂时无法登录，请检查网络后重试'
  } finally {
    busy.value = false
  }
}
onMounted(restore)
</script>

<style scoped lang="scss">
.auth-shell {
  min-height: 100vh;
  min-height: 100dvh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px 24px calc(48px + env(safe-area-inset-bottom));
  background: var(--color-bg);
}
.auth-page {
  width: 100%;
  max-width: 380px;
}
.auth-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--color-text-primary);
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 32px;
}
.auth-title {
  display: block;
  margin: 0;
  font-size: 26px;
  font-weight: 600;
  line-height: 1.4;
  letter-spacing: -0.02em;
  color: var(--color-text-primary);
}
.auth-form {
  margin-top: 32px;
}
.auth-form :deep(.account-field:first-child) {
  margin-top: 0;
}
.auth-form :deep(.field-input:not(:focus)) {
  border-color: var(--color-border);
}
.auth-form .primary-btn {
  margin-top: 28px;
}
.auth-links {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  color: var(--color-primary);
  font-size: 14px;
  margin-top: 16px;
}
.auth-links button {
  display: inline-flex;
  align-items: center;
  min-height: 44px;
  margin: 0;
  padding: 0;
  background: transparent;
  color: inherit;
  font-size: inherit;
  text-align: left;
  cursor: pointer;
}
.auth-links .auth-password-link {
  color: var(--color-text-secondary);
}
@media (max-width: 480px) {
  .auth-shell {
    align-items: flex-start;
    padding-top: calc(80px + env(safe-area-inset-top));
  }
}
@media (max-height: 600px) {
  .auth-shell {
    padding-top: 24px;
  }
  .auth-brand {
    margin-bottom: 24px;
  }
}
</style>
