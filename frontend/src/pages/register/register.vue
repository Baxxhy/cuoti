<template>
  <view class="page">
    <app-header title="创建账号" back back-fallback="/pages/login/login" />

    <view class="page-content">
      <view class="card">
        <account-field
          id="register-name"
          v-model="form.name"
          label="你的名字"
          autocomplete="nickname"
          placeholder="请输入昵称"
          :maxlength="100"
        />
        <account-field
          id="register-email"
          v-model="form.email"
          label="邮箱"
          inputmode="email"
          autocomplete="username"
          placeholder="student@example.com"
        />
        <account-field
          id="register-password"
          v-model="form.password"
          label="登录密码"
          type="password"
          autocomplete="new-password"
          placeholder="请输入密码"
          :described-by="notice ? 'register-notice' : undefined"
        />

        <!-- 年级 -->
        <view class="field">
          <!-- #ifdef H5 -->
          <component :is="'label'" class="field-label" for="register-grade">当前年级</component>
          <component
            :is="'select'"
            id="register-grade"
            class="field-picker grade-select"
            :value="form.grade"
            @change="form.grade = $event.target.value"
          >
            <component :is="'option'" value="" disabled>请选择当前年级</component>
            <component :is="'option'" v-for="grade in grades" :key="grade" :value="grade">
              {{ grade }}
            </component>
          </component>
          <!-- #endif -->
          <!-- #ifndef H5 -->
          <text class="field-label">当前年级</text>
          <picker :range="grades" aria-label="当前年级" @change="handleGradeChange">
            <view class="field-picker">
              <text :class="form.grade ? 'picker-value' : 'picker-placeholder'">
                {{ form.grade || '请选择当前年级' }}
              </text>

              <view class="picker-arrow"></view>
            </view>
          </picker>
          <!-- #endif -->
        </view>

        <text v-if="notice" id="register-notice" class="account-notice" role="alert">
          {{ notice }}
        </text>
        <!-- 创建 -->
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
          {{ busy ? '正在创建…' : '创建账号' }}
        </button>
      </view>
    </view>
  </view>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import AccountField from '@/components/account-field/account-field.vue'
import { MIDDLE_SCHOOL_GRADES as grades } from '@/constants/education.js'
import { useAppStore } from '@/store/index.js'

const store = useAppStore()
const busy = ref(false)
const notice = ref('')

const form = reactive({
  name: '',
  email: '',
  password: '',
  grade: '',
})

const canSubmit = computed(
  () => !!(form.name.trim() && form.email.trim() && form.password && form.grade),
)

function handleGradeChange(e) {
  form.grade = grades[e.detail.value]
}

async function submit() {
  if (!canSubmit.value || busy.value) return
  notice.value = ''
  busy.value = true

  try {
    await store.register({ ...form, name: form.name.trim(), email: form.email.trim() })

    uni.reLaunch({
      url: '/pages/index/index',
    })
  } catch (err) {
    notice.value = err.message || '暂时无法创建账号，请检查网络后重试'
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.page-content {
  max-width: 500px;
}
.card {
  padding: 24px;
}
.field:first-child {
  margin-top: 0;
}
.field-picker {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.grade-select {
  display: block;
  height: calc(1.5em + 26px);
  min-height: 50px;
  font-family: inherit;
  font-size: 16px;
  line-height: 1.5;
}
.input-placeholder,
.picker-placeholder {
  color: var(--color-text-tertiary);
}
.picker-arrow {
  width: 7px;
  height: 7px;
  border-right: 1.5px solid var(--color-text-secondary);
  border-bottom: 1.5px solid var(--color-text-secondary);
  transform: rotate(45deg);
  margin: -4px 4px 0 12px;
}
</style>
