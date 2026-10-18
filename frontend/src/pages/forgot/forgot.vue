<template>
  <view class="page">
    <app-header title="修改登录密码" back back-fallback="/pages/login/login" />
    <view class="page-content">
      <view class="card">
        <text class="muted">验证当前密码后，为账号设置新密码。</text>
        <account-field
          id="change-email"
          v-model="email"
          label="账号邮箱"
          inputmode="email"
          autocomplete="username"
          placeholder="student@example.com"
        />
        <account-field
          id="change-current"
          v-model="currentPassword"
          label="当前密码"
          type="password"
          autocomplete="current-password"
          placeholder="请输入当前密码"
        />
        <account-field
          id="change-password"
          v-model="password"
          label="新密码"
          type="password"
          autocomplete="new-password"
          placeholder="至少 6 位"
          hint="至少 6 位，请勿与当前密码相同。"
        />
        <account-field
          id="change-confirmation"
          v-model="confirmation"
          label="确认新密码"
          type="password"
          autocomplete="new-password"
          placeholder="再次输入新密码"
          :described-by="notice ? 'change-notice' : undefined"
          @confirm="submit"
        />
        <text v-if="notice" id="change-notice" class="account-notice" role="alert">
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
          {{ busy ? '正在保存…' : '修改密码' }}
        </button>
      </view>
    </view>
  </view>
</template>
<script setup>
import { computed, ref } from 'vue'
import { postData } from '@/api/index.js'
import AccountField from '@/components/account-field/account-field.vue'
const email = ref(''),
  currentPassword = ref(''),
  password = ref(''),
  confirmation = ref(''),
  busy = ref(false),
  notice = ref('')
const canSubmit = computed(
  () => email.value && currentPassword.value && password.value.length >= 6 && confirmation.value,
)
async function submit() {
  if (!canSubmit.value || busy.value) return
  if (password.value !== confirmation.value) {
    notice.value = '两次输入的新密码不一致'
    return
  }
  if (password.value === currentPassword.value) {
    notice.value = '新密码不能与当前密码相同'
    return
  }
  busy.value = true
  notice.value = ''
  try {
    await postData(
      '/auth/reset-password',
      {
        email: email.value.trim(),
        current_password: currentPassword.value,
        new_password: password.value,
      },
      { skipAuthRedirect: true },
    )
    uni.removeStorageSync('minddimension_access_token')
    uni.showToast({ title: '密码已更新，请重新登录', icon: 'none' })
    uni.reLaunch({ url: '/pages/login/login' })
  } catch (err) {
    notice.value = err.message || '修改失败，请重试'
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.page-content {
  max-width: 500px;
}
</style>
