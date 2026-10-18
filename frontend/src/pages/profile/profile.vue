<template>
  <view class="page profile-page">
    <app-header title="我的" />
    <view class="page-content">
      <state-panel
        v-if="loading || error"
        :state="error ? 'error' : 'loading'"
        :message="error"
        @retry="load"
      />
      <template v-else>
        <view class="student-profile">
          <view class="avatar">
            <text v-if="store.user?.name">{{ store.user.name.slice(0, 1) }}</text>
            <uni-icons v-else type="person" size="28" color="#55565B" />
          </view>
          <view class="list-main">
            <text class="profile-name">{{ store.user?.name || '当前用户' }}</text>
            <text v-if="store.role === 'student'" class="profile-meta">
              {{ dashboard.grade || store.user?.grade || '年级未设置' }}
              <template v-if="dashboard.streak_days">
                · 连续学习 {{ dashboard.streak_days }} 天
              </template>
            </text>
            <text v-else class="profile-meta">{{ roleName }}</text>
          </view>
        </view>
        <template v-if="store.role === 'student'">
          <button
            aria-label="学习方向"
            role="button"
            tabindex="0"
            class="disclosure-link"
            @keydown.enter.prevent="go('/pages/preferences/preferences')"
            @keydown.space.prevent
            @keyup.space.prevent="go('/pages/preferences/preferences')"
            @click="go('/pages/preferences/preferences')"
          >
            学习方向
            <uni-icons type="right" size="18" />
          </button>
          <view class="section-title"><text>使用与帮助</text></view>
          <view class="setting-list">
            <view
              v-for="item in studentSettings"
              :key="item.url"
              class="setting-row"
              @click="go(item.url)"
            >
              <uni-icons :type="item.icon" size="24" color="#55565B" />
              <view class="list-main">
                <text class="setting-title">{{ item.title }}</text>
                <text class="setting-desc">{{ item.desc }}</text>
              </view>
              <uni-icons type="right" size="22" color="#85868B" />
            </view>
          </view>
        </template>
        <view v-else class="setting-list role-settings">
          <view
            v-for="item in roleSettings"
            :key="item.url"
            class="setting-row"
            @click="go(item.url)"
          >
            <uni-icons :type="item.icon" size="24" color="#55565B" />
            <view class="list-main">
              <text class="setting-title">{{ item.title }}</text>
            </view>
            <uni-icons type="right" size="22" color="#85868B" />
          </view>
        </view>
        <button class="secondary-btn logout-button" @click="store.logout()">退出登录</button>
      </template>
    </view>
    <tab-bar v-if="store.role === 'student'" current="profile" />
  </view>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { getData } from '@/api/index.js'
import { useAppStore } from '@/store/index.js'
import { go } from '@/utils/navigation.js'
const store = useAppStore(),
  dashboard = ref({}),
  loading = ref(true),
  error = ref('')
const roleNames = { guardian: '家长中心', teacher: '教师中心', admin: '系统管理' }
const roleName = computed(() => roleNames[store.role] || '学习档案')
const studentSettings = [
  {
    title: '家长查看权限',
    desc: '授权或解除家长的报告查看权限',
    icon: 'staff',
    url: '/pages/guardian/access',
  },
  {
    title: '使用指南',
    desc: '了解录入、诊断、练习与复习的区别',
    icon: 'help',
    url: '/pages/help/help',
  },
  {
    title: '学习中心',
    desc: '复习巩固、专项备考、知识与学情',
    icon: 'book',
    url: '/pages/learning/learning',
  },
]
const roleSettings = computed(
  () =>
    ({
      guardian: [{ title: '返回家长中心', icon: 'staff', url: '/pages/guardian/home' }],
      teacher: [{ title: '返回教师中心', icon: 'person', url: '/pages/teacher/classes' }],
      admin: [{ title: '系统状态', icon: 'gear', url: '/pages/system/system' }],
    })[store.role] || [],
)
async function load() {
  loading.value = true
  error.value = ''
  try {
    await store.loadUser()
    if (store.role === 'student') dashboard.value = await getData('/dashboard')
  } catch (err) {
    error.value = err.message || '个人档案暂时无法加载，请重试'
  } finally {
    loading.value = false
  }
}
onMounted(load)
</script>

<style scoped lang="scss">
.student-profile {
  display: flex;
  align-items: center;
  gap: 22rpx;
  padding: 16rpx 0 30rpx;
  border-bottom: 1rpx solid var(--color-border);
}
.avatar {
  width: 88rpx;
  height: 88rpx;
  flex: none;
  border: 1rpx solid var(--color-border);
  border-radius: 16rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-surface);
  color: var(--color-text-primary);
  font-size: 34rpx;
  font-weight: 500;
}
.profile-name,
.profile-meta {
  display: block;
}
.profile-name {
  font-size: 34rpx;
  line-height: 1.4;
  font-weight: 600;
}
.profile-meta {
  font-size: 24rpx;
  color: var(--color-text-secondary);
  margin-top: 6rpx;
}
.section-title {
  margin: 34rpx 0 12rpx;
}
.section-title > text:first-child {
  font-size: 25rpx;
  font-weight: 500;
  color: var(--color-text-secondary);
}
.setting-list {
  border-top: 1rpx solid var(--color-border);
}
.setting-row {
  display: flex;
  align-items: center;
  gap: 20rpx;
  min-height: 120rpx;
  padding: 22rpx 0;
  border-bottom: 1rpx solid var(--color-border);
}
.setting-title,
.setting-desc {
  display: block;
}
.setting-title {
  font-size: 28rpx;
  font-weight: 500;
}
.setting-desc {
  font-size: 24rpx;
  color: var(--color-text-secondary);
  margin-top: 4rpx;
}
.role-settings {
  margin-top: 30rpx;
}
.logout-button {
  margin-top: 48rpx;
  border: 1rpx solid var(--color-border);
  background: var(--color-surface);
  color: var(--color-text-secondary);
  font-size: 27rpx;
  font-weight: 500;
}
</style>
