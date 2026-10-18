<template>
  <view class="page">
    <app-header title="家长中心" subtitle="了解孩子最近的学习情况" gradient>
      <view
        class="header-link"
        role="button"
        tabindex="0"
        aria-label="个人中心"
        @click="go('/pages/profile/profile')"
        @keydown.enter="go('/pages/profile/profile')"
      >
        <uni-icons type="person" size="24" color="var(--color-text-secondary)" />
      </view>
    </app-header>
    <view class="page-content">
      <state-panel
        v-if="loading || error"
        :state="error ? 'error' : 'loading'"
        :message="error"
        @retry="load"
      />
      <template v-else>
        <view class="section-title"><text>我的孩子</text></view>
        <view v-for="student in students" :key="student.id" class="student-card">
          <view
            class="student-link"
            role="button"
            tabindex="0"
            :aria-label="`查看${student.name}的学习报告`"
            @click="go(`/pages/guardian/report?id=${student.id}`)"
            @keydown.enter="go(`/pages/guardian/report?id=${student.id}`)"
            @keydown.space.prevent="go(`/pages/guardian/report?id=${student.id}`)"
          >
            <view class="student-avatar">{{ student.name.slice(0, 1) }}</view>
            <view class="list-main">
              <text class="list-title">{{ student.name }}</text>
              <text class="list-desc">
                平均掌握 {{ Math.round(student.average_mastery * 100) }}%
              </text>
              <view class="progress">
                <view :style="{ width: student.average_mastery * 100 + '%' }" />
              </view>
            </view>
            <view class="review-pill">
              <b>{{ student.pending_reviews }}</b>
              <text>待复习</text>
            </view>
          </view>
          <button class="secondary-btn unlink" :disabled="busy" @click="unlink(student)">
            解除关联
          </button>
        </view>
        <view v-if="!students.length" class="empty"><text>还没有可查看的学生档案</text></view>
        <text class="access-note">请让学生在“我的 → 家长查看权限”中授权你的家长账号邮箱。</text>
        <text v-if="actionError" role="alert" class="access-note">{{ actionError }}</text>
      </template>
    </view>
  </view>
</template>
<script setup>
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { getData, deleteData } from '@/api/index.js'
import { go } from '@/utils/navigation.js'
const students = ref([]),
  loading = ref(true)
async function loadData() {
  students.value = await getData('/guardians/students')
}
onShow(load)
const error = ref(''),
  busy = ref(false),
  actionError = ref('')
function unlink(student) {
  if (busy.value) return
  uni.showModal({
    title: '解除关联？',
    content: `解除后将不能查看${student.name}的学习报告。学生的记录会保留。`,
    confirmText: '确认解除',
    success: async ({ confirm }) => {
      if (!confirm || busy.value) return
      busy.value = true
      actionError.value = ''
      try {
        await deleteData(`/guardians/students/${student.id}`, { silent: true })
        await load()
        uni.showToast({ title: '已解除关联', icon: 'none' })
      } catch (err) {
        actionError.value = err.message || '解除失败，请重试'
      } finally {
        busy.value = false
      }
    },
  })
}
async function load() {
  loading.value = true
  error.value = ''
  try {
    await loadData()
  } catch (err) {
    error.value = err.message || '暂时无法加载，请重试'
  } finally {
    loading.value = false
  }
}
</script>
<style scoped lang="scss">
.student-card {
  display: block;
  gap: 20rpx;
  align-items: center;
  padding: 28rpx;
  background: #fff;
  border-radius: 24rpx;
}
.student-link {
  display: flex;
  gap: 20rpx;
  align-items: center;
  min-height: 96rpx;
}
.student-link .list-main {
  min-width: 0;
  overflow-wrap: anywhere;
}
.student-link .student-avatar,
.review-pill {
  flex: none;
}
.unlink {
  margin-top: 24rpx;
}
.access-note {
  display: block;
  margin: 24rpx 0;
  color: var(--color-text-secondary);
  line-height: 1.6;
  font-size: 28rpx;
}
.student-avatar {
  width: 85rpx;
  height: 85rpx;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #eaf7f2;
  color: #008258;
  font-size: 32rpx;
  font-weight: 700;
}
.student-card .progress {
  margin-top: 12rpx;
}
.review-pill {
  text-align: center;
}
.review-pill b,
.review-pill text {
  display: block;
}
.review-pill b {
  font-size: 33rpx;
  color: #f59e0b;
}
.review-pill text {
  font-size: 20rpx;
  color: #94a3b8;
}
</style>
