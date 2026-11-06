<template>
  <view class="page edit-profile-page">
    <app-header title="编辑个人资料" back back-fallback="/pages/profile/profile" />
    <view class="page-content">
      <state-panel
        v-if="loading || loadError"
        :state="loadError ? 'error' : 'loading'"
        :message="loadError"
        @retry="load"
      />
      <view v-else class="profile-form">
        <text class="field-label">昵称</text>
        <input
          class="field-input"
          aria-label="昵称"
          v-model="name"
          maxlength="100"
          :disabled="saving"
          placeholder="填写昵称"
        />
        <text class="field-label">邮箱</text>
        <input
          class="field-input"
          aria-label="邮箱"
          v-model="email"
          :disabled="saving"
          placeholder="填写登录邮箱"
        />
        <text v-if="emailChanged" class="field-note">保存后请使用新邮箱登录。</text>
        <template v-if="emailChanged">
          <text class="field-label">当前密码</text>
          <input
            class="field-input"
            aria-label="当前密码"
            v-model="password"
            password
            :disabled="saving"
            placeholder="修改登录邮箱需要验证密码"
          />
        </template>
        <template v-if="store.role === 'student'">
          <text class="field-label">年级</text>
          <!-- #ifdef H5 -->
          <component
            :is="'select'"
            class="field-input"
            aria-label="年级"
            :value="grade"
            :disabled="saving"
            @change="grade = $event.target.value"
          >
            <component :is="'option'" value="" disabled>请选择年级</component>
            <component :is="'option'" v-for="item in grades" :key="item" :value="item">
              {{ item }}
            </component>
          </component>
          <!-- #endif -->
          <!-- #ifndef H5 -->
          <picker :range="grades" :disabled="saving" @change="grade = grades[$event.detail.value]">
            <view class="field-input">{{ grade || '请选择年级' }}</view>
          </picker>
          <!-- #endif -->
        </template>
        <text v-if="error" class="save-error" role="alert">{{ error }}</text>
        <text v-if="saved" class="save-success" role="status">已保存</text>
        <button
          role="button"
          class="primary-btn"
          tabindex="0"
          @keydown.enter.prevent="save"
          @keydown.space.prevent
          @keyup.space.prevent="save"
          :disabled="saving"
          @click="save"
        >
          {{ saving ? '正在保存…' : '保存资料' }}
        </button>
      </view>
    </view>
  </view>
</template>
<script setup>
import { computed, ref, watch, nextTick } from 'vue'
import { onLoad, onUnload } from '@dcloudio/uni-app'
import { getData, patchData } from '@/api/index.js'
import { useAppStore } from '@/store/index.js'
import { MIDDLE_SCHOOL_GRADES as grades } from '@/constants/education.js'
const store = useAppStore()
const name = ref(''),
  email = ref(''),
  originalEmail = ref(''),
  grade = ref(''),
  password = ref(''),
  loading = ref(true),
  loadError = ref(''),
  error = ref(''),
  saved = ref(false),
  saving = ref(false)
const emailChanged = computed(() => email.value.trim() !== originalEmail.value)
watch([name, email, grade, password], () => {
  saved.value = false
})
let active = true
async function load() {
  loading.value = true
  loadError.value = ''
  try {
    const user = await store.loadUser()
    const preferences = store.role === 'student' ? await getData('/student-preferences') : null
    if (!active) return
    name.value = user.name || ''
    email.value = originalEmail.value = user.email || ''
    grade.value = preferences?.grade || ''
  } catch (e) {
    if (active) loadError.value = e.message || '资料读取失败，请重试'
  } finally {
    if (active) loading.value = false
  }
}
async function save() {
  if (saving.value) return
  error.value = ''
  saved.value = false
  if (!name.value.trim()) {
    error.value = '请填写昵称'
    return
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value.trim())) {
    error.value = '请填写正确的邮箱'
    return
  }
  if (store.role === 'student' && !grades.includes(grade.value)) {
    error.value = '请选择年级'
    return
  }
  if (emailChanged.value && !password.value) {
    error.value = '请输入当前密码'
    return
  }
  saving.value = true
  try {
    const user = await patchData('/auth/me', {
      name: name.value.trim(),
      email: email.value.trim(),
      ...(store.role === 'student' ? { grade: grade.value } : {}),
      ...(emailChanged.value ? { current_password: password.value } : {}),
    })
    if (!active) return
    store.user = user
    originalEmail.value = user.email
    email.value = user.email
    password.value = ''
    await nextTick()
    saved.value = true
  } catch (e) {
    if (active) error.value = e.message || '保存失败，请重试'
  } finally {
    if (active) saving.value = false
  }
}
onLoad(load)
onUnload(() => {
  active = false
  password.value = ''
})
</script>
<style scoped>
.edit-profile-page {
  max-width: 640px;
}
.profile-form {
  padding: 4px 0;
}
.field-label {
  display: block;
  font-size: 14px;
  color: var(--color-text-secondary);
  margin: 20px 0 8px;
}
.field-input {
  width: 100%;
  box-sizing: border-box;
  background: var(--color-surface);
  min-height: 48px;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  padding: 12px;
  font-size: 16px;
  color: var(--color-text-primary);
}
.field-note {
  display: block;
  font-size: 13px;
  color: var(--color-text-secondary);
  margin-top: 8px;
}
.save-error,
.save-success {
  display: block;
  font-size: 14px;
  margin-top: 20px;
}
.save-error {
  color: var(--color-error);
}
.save-success {
  color: var(--color-success);
}
.primary-btn {
  margin-top: 28px;
}
</style>
