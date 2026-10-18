<template>
  <view class="teacher-page">
    <app-header title="教师工作台" subtitle="先处理需要你判断的学习证据" gradient>
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
    <view class="teacher-content">
      <state-panel
        v-if="loading || error"
        :state="error ? 'error' : 'loading'"
        :message="error"
        @retry="load"
      />
      <template v-else>
        <view class="teacher-grid">
          <view
            v-for="item in metrics"
            :key="item.label"
            class="metric-card"
            @click="item.url && go(item.url)"
          >
            <text class="metric-value">{{ item.value }}</text>
            <text class="metric-label">{{ item.label }}</text>
          </view>
        </view>
        <view class="teacher-card">
          <view class="card-heading"><text>快捷入口</text></view>
          <view class="teacher-actions">
            <button class="primary" @click="go('/pages/teacher/reviews')">待核对队列</button>
            <button @click="go('/pages/teacher/classes')">班级与学生</button>
            <button @click="go('/pages/teacher/questions')">题目管理</button>
            <button @click="go('/pages/teacher/assignment')">布置记录</button>
            <button @click="go('/pages/teacher/audit')">操作记录</button>
          </view>
        </view>
        <view class="two-column">
          <view class="teacher-card">
            <view class="card-heading"><text>薄弱知识点</text></view>
            <view v-for="item in data.weak_points" :key="item.name" class="teacher-row">
              <view class="row-main">
                <text class="row-title">{{ item.name }}</text>
                <text class="row-meta">班级掌握 {{ Math.round(item.score * 100) }}%</text>
              </view>
            </view>
            <text v-if="!data.weak_points?.length" class="muted">暂无掌握证据</text>
          </view>
          <view class="teacher-card">
            <view class="card-heading"><text>高频错因</text></view>
            <view v-for="item in data.frequent_errors" :key="item.name" class="teacher-row">
              <view class="row-main">
                <text class="row-title">{{ item.name }}</text>
                <text class="row-meta">出现概率 {{ Math.round(item.probability * 100) }}%</text>
              </view>
            </view>
            <text v-if="!data.frequent_errors?.length" class="muted">暂无错因记录</text>
          </view>
        </view>
        <view class="teacher-card">
          <view class="card-heading">
            <text>最近需要关注</text>
            <text class="card-link" @click="go('/pages/teacher/reviews')">全部待核对</text>
          </view>
          <view v-for="item in data.attention_students" :key="item.id" class="teacher-row">
            <view class="row-main">
              <text class="row-title">{{ item.name }}</text>
              <text class="row-meta">{{ item.pending_reviews }} 个作答等待核对</text>
            </view>
            <text class="tag warn">需关注</text>
          </view>
          <text v-if="!data.attention_students?.length" class="muted">目前没有等待处理的学生</text>
        </view>
      </template>
    </view>
  </view>
</template>
<script setup>
import { computed, onMounted, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { getData } from '@/api/index.js'
import { go } from '@/utils/navigation.js'
const data = ref({}),
  loading = ref(true)
const metrics = computed(() => [
  { label: '待核对作答', value: data.value.pending_reviews || 0, url: '/pages/teacher/reviews' },
  { label: '今日新增错题', value: data.value.today_mistakes || 0 },
  { label: '计划逾期学生', value: data.value.overdue_students || 0, url: '/pages/teacher/classes' },
  {
    label: '布置未完成',
    value: data.value.unfinished_assignments || 0,
    url: '/pages/teacher/assignment',
  },
])
async function loadData() {
  data.value = await getData('/teachers/dashboard')
}
onShow(load)
const error = ref('')
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
<style lang="scss">
@import './teacher.scss';
</style>
