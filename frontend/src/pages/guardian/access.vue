<template>
  <view class="page">
    <app-header title="家长查看权限" back />
    <view class="page-content">
      <text class="access-note">由你决定谁能查看学习报告。家长不能修改你的作答或学习记录。</text>
      <state-panel
        v-if="loading || error"
        :state="error ? 'error' : 'loading'"
        :message="error"
        @retry="load"
      />
      <template v-else>
        <view v-for="guardian in guardians" :key="guardian.id" class="access-row">
          <view class="list-main">
            <text class="list-title">{{ guardian.name }}</text>
            <text class="list-desc">{{ guardian.email }}</text>
          </view>
          <button class="secondary-btn" :disabled="busy" @click="remove(guardian)">解除</button>
        </view>
        <text v-if="!guardians.length" class="access-note">还没有家长可以查看你的报告。</text>
        <view class="grant-form">
          <text class="list-title">允许一位家长查看</text>
          <text class="access-note">请先确认家长已有家长账号，再填写对方邮箱。</text>
          <input
            v-model="email"
            aria-label="家长账号邮箱"
            placeholder="家长账号邮箱"
            :disabled="busy"
            maxlength="190"
          />
          <button class="primary-btn" :disabled="busy || !email.trim()" @click="grant">
            核对并授权
          </button>
          <text v-if="actionError" class="action-error" role="alert">{{ actionError }}</text>
        </view>
      </template>
    </view>
  </view>
</template>
<script setup>
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { getData, postData, deleteData } from '@/api/index.js'
const guardians = ref([]),
  email = ref(''),
  loading = ref(true),
  busy = ref(false),
  error = ref(''),
  actionError = ref('')
async function load() {
  loading.value = true
  error.value = ''
  try {
    guardians.value = await getData('/students/guardian-links', { silent: true })
  } catch (err) {
    guardians.value = []
    error.value = err.message || '查看权限暂时无法加载'
  } finally {
    loading.value = false
  }
}
async function change(operation, message) {
  if (busy.value) return
  busy.value = true
  actionError.value = ''
  try {
    await operation()
    uni.showToast({ title: message, icon: 'none' })
    await load()
  } catch (err) {
    actionError.value = err.message || '暂时无法保存，请重试'
  } finally {
    busy.value = false
  }
}
function grant() {
  const value = email.value.trim()
  if (!value || busy.value) return
  uni.showModal({
    title: '允许查看学习报告？',
    content: `授权给 ${value}。对方可以查看掌握情况、错因和学习统计；你随时可以解除。`,
    confirmText: '确认授权',
    success: ({ confirm }) => {
      if (confirm)
        change(async () => {
          await postData(
            '/students/guardian-links',
            { email: value, confirmed: true },
            { silent: true },
          )
          email.value = ''
        }, '已允许查看')
    },
  })
}
function remove(guardian) {
  if (busy.value) return
  uni.showModal({
    title: '解除查看权限？',
    content: `${guardian.name}将不能再读取你的学习报告。学习记录会保留。`,
    confirmText: '确认解除',
    success: ({ confirm }) => {
      if (confirm)
        change(
          () => deleteData(`/students/guardian-links/${guardian.id}`, { silent: true }),
          '已解除查看权限',
        )
    },
  })
}
onShow(load)
</script>
<style scoped lang="scss">
.access-note {
  display: block;
  color: var(--color-text-secondary);
  font-size: 28rpx;
  line-height: 1.6;
  margin: 20rpx 0;
}
.access-row {
  display: flex;
  align-items: center;
  gap: 20rpx;
  padding: 24rpx 0;
  border-bottom: 1rpx solid var(--color-border);
}
.access-row .list-main {
  min-width: 0;
  overflow-wrap: anywhere;
}
.access-row button {
  flex: none;
  min-width: 120rpx;
}
.grant-form {
  margin-top: 32rpx;
}
.grant-form input {
  min-height: 96rpx;
  border: 1rpx solid var(--color-border);
  border-radius: 16rpx;
  padding: 0 24rpx;
  margin-bottom: 24rpx;
  font-size: 32rpx;
}
.action-error {
  display: block;
  color: var(--color-error);
  margin-top: 16rpx;
}
</style>
