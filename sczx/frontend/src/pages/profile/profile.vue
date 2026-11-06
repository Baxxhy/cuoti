<template>
  <div class="page profile-page">
    <app-header title="我的" />
    <div class="page-content">
      <state-panel
        v-if="loading || error"
        :state="error ? 'error' : 'loading'"
        :message="error"
        @retry="load"
      />
      <template v-else>
        <div class="student-profile">
          <div class="avatar">
            <span v-if="store.user?.name">{{ store.user.name.slice(0, 1) }}</span>
            <WebIcon aria-hidden="true" v-else type="person" size="28" color="#55565B" />
          </div>
          <div class="list-main">
            <span class="profile-name">{{ store.user?.name || '当前用户' }}</span>
            <span v-if="store.role === 'student'" class="profile-meta">
              {{ dashboard.grade || store.user?.grade || '年级未设置' }}
            </span>
            <span v-else class="profile-meta">{{ roleName }}</span>
          </div>
        </div>
        <button
          class="edit-profile-link disclosure-link"
          tabindex="0"
          @keydown.enter.prevent="go('/pages/profile/edit')"
          @keydown.space.prevent
          @keyup.space.prevent="go('/pages/profile/edit')"
          role="button"
          @click="go('/pages/profile/edit')"
        >
          <span>编辑个人资料</span>
          <WebIcon type="right" size="18" aria-hidden="true" />
        </button>
        <template v-if="store.role === 'student'">
          <button
            aria-label="学习设置"
            role="button"
            tabindex="0"
            class="disclosure-link"
            @keydown.enter.prevent="go('/pages/preferences/preferences')"
            @keydown.space.prevent
            @keyup.space.prevent="go('/pages/preferences/preferences')"
            @click="go('/pages/preferences/preferences')"
          >
            学习设置
            <WebIcon aria-hidden="true" type="right" size="18" />
          </button>
          <div class="section-title"><span>使用与帮助</span></div>
          <div class="setting-list">
            <button
              role="button"
              tabindex="0"
              @keydown.enter.prevent="go(item.url)"
              @keydown.space.prevent
              @keyup.space.prevent="go(item.url)"
              v-for="item in studentSettings"
              :key="item.url"
              class="setting-row"
              @click="go(item.url)"
            >
              <WebIcon aria-hidden="true" :type="item.icon" size="24" color="#55565B" />
              <div class="list-main">
                <span class="setting-title">{{ item.title }}</span>
              </div>
              <WebIcon aria-hidden="true" type="right" size="22" color="#85868B" />
            </button>
          </div>
        </template>
        <div v-else class="setting-list role-settings">
          <button
            role="button"
            tabindex="0"
            @keydown.enter.prevent="go(item.url)"
            @keydown.space.prevent
            @keyup.space.prevent="go(item.url)"
            v-for="item in roleSettings"
            :key="item.url"
            class="setting-row"
            @click="go(item.url)"
          >
            <WebIcon aria-hidden="true" :type="item.icon" size="24" color="#55565B" />
            <div class="list-main">
              <span class="setting-title">{{ item.title }}</span>
            </div>
            <WebIcon aria-hidden="true" type="right" size="22" color="#85868B" />
          </button>
        </div>
        <button role="button" class="secondary-btn logout-button" @click="store.logout()">
          退出登录
        </button>
      </template>
    </div>
    <tab-bar v-if="store.role === 'student'" current="profile" />
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { onShow, onHide, onUnload } from '@/platform/lifecycle.js'
import { getData } from '@/api/index.js'
import { useAppStore } from '@/store/index.js'
import { go } from '@/utils/navigation.js'
const store = useAppStore(),
  dashboard = ref({}),
  loading = ref(true),
  error = ref('')
const roleNames = { admin: '系统管理' }
const roleName = computed(() => roleNames[store.role] || '学习档案')
const studentSettings = [
  {
    title: '使用指南',
    desc: '了解录入、诊断、练习与复习的区别',
    icon: 'help',
    url: '/pages/help/help',
  },
]
const roleSettings = computed(
  () =>
    ({
      admin: [{ title: '系统状态', icon: 'gear', url: '/pages/system/system' }],
    })[store.role] || [],
)
let revision = 0
async function load() {
  const current = ++revision
  loading.value = true
  error.value = ''
  try {
    await store.loadUser()
    const result = store.role === 'student' ? await getData('/dashboard') : {}
    if (current === revision) dashboard.value = result
  } catch (err) {
    if (current === revision) error.value = err.message || '个人档案暂时无法加载，请重试'
  } finally {
    if (current === revision) loading.value = false
  }
}
onShow(load)
onHide(() => revision++)
onUnload(() => revision++)
</script>

<style scoped lang="scss">
.edit-profile-link {
  margin-bottom: 12px;
}

.student-profile {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 16px 0;
  margin-bottom: 24px;
}
.avatar {
  width: 64px;
  height: 64px;
  flex: none;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-size: 21px;
  font-weight: 500;
}
.profile-name,
.profile-meta {
  display: block;
}
.profile-name {
  font-size: 23px;
  line-height: 1.35;
  font-weight: 600;
  letter-spacing: -0.02em;
  overflow-wrap: anywhere;
}
.profile-meta {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin-top: 6px;
}
.disclosure-link {
  padding: 18px 24px;
  border: 0;
  border-radius: 12px;
  background: var(--color-surface);
}
.section-title {
  margin: 28px 24px 10px;
}
.section-title > span:first-child {
  font-size: 13px;
  font-weight: 400;
  color: var(--color-text-secondary);
}
.setting-list {
  padding: 0 24px;
  border-radius: 12px;
  background: var(--color-surface);
}
.setting-row {
  width: 100%;
  margin: 0;
  border-radius: 0;
  background: transparent;
  text-align: left;
  line-height: 1.5;
  display: flex;
  align-items: center;
  gap: 16px;
  min-height: 64px;
  padding: 16px 0;
  cursor: pointer;
}
.setting-row + .setting-row {
  border-top: 1px solid var(--color-border);
}
.setting-title {
  display: block;
  font-size: 16px;
  font-weight: 400;
}
.role-settings {
  margin-top: 24px;
}
.logout-button {
  margin-top: 24px;
  background: var(--color-surface);
  color: var(--color-error);
  font-size: 16px;
  font-weight: 400;
  border-radius: 12px;
}
</style>
