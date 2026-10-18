<template>
  <view class="auth-shell">
    <view class="auth-page">
      <view class="auth-top">
        <text class="auth-brand">错题帮</text>
        <text class="auth-title">欢迎回来</text>
        <text class="auth-subtitle">登录账号，继续你的学习。</text>
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
}
.auth-page {
  min-height: 100vh;
  min-height: 100dvh;
  width: 100%;
  max-width: 460px;
  margin: 0 auto;
  padding: calc(72px + env(safe-area-inset-top)) 28px calc(40px + env(safe-area-inset-bottom));
  background: #fff;
}
.auth-top {
  text-align: left;
}
.auth-brand {
  display: block;
  color: var(--color-primary);
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 36px;
}
.auth-title,
.auth-subtitle {
  display: block;
}
.auth-title {
  font-size: 28px;
  font-weight: 600;
  color: var(--color-text-primary);
}
.auth-subtitle {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin-top: 8px;
}
.auth-form {
  margin-top: 32px;
}
.auth-form .primary-btn {
  margin-top: 28px;
}
.auth-links {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  color: var(--color-primary);
  font-size: 13px;
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
@media (min-width: 768px) {
  .auth-shell {
    padding: 64px 24px;
  }
  .auth-page {
    min-height: 0;
    margin: 0 auto;
    padding: 40px;
    border: 1px solid var(--color-border);
    border-radius: 12px;
  }
}
@media (max-height: 600px) {
  .auth-page {
    padding-top: 28px;
  }
  .auth-brand {
    margin-bottom: 24px;
  }
}
</style>
