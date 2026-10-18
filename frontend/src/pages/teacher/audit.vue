<template>
  <view class="teacher-page">
    <app-header title="教师操作记录" subtitle="人工修改可追踪，不覆盖原始数据" back />
    <view class="teacher-content">
      <state-panel
        v-if="loading || error"
        :state="error ? 'error' : 'loading'"
        :message="error"
        @retry="load"
      />
      <view v-else class="teacher-card">
        <view v-for="item in items" :key="item.id" class="teacher-row">
          <view class="row-main">
            <text class="row-title">{{ label(item.action) }}</text>
            <text class="row-meta">
              {{ new Date(item.created_at).toLocaleString('zh-CN', { hour12: false }) }} ·
              {{ item.target_type }} /
              {{ item.target_id }}
            </text>
            <text class="row-meta">原因：{{ item.reason || '未填写' }}</text>
          </view>
        </view>
        <view v-if="!items.length" class="empty-card">暂无教师操作记录</view>
      </view>
    </view>
  </view>
</template>
<script setup>
import { onMounted, ref } from 'vue'
import { getData } from '@/api/index.js'
const items = ref([]),
  loading = ref(true),
  labels = {
    'class.create': '创建班级',
    'class.student.add': '添加学生',
    'class.student.remove': '移除学生',
    'review.decision': '人工复核',
    'review.revoke': '撤销复核',
    'question.create': '创建题目',
    'assignment.create': '布置题目',
    'plan.update': '调整学习计划',
  }
const label = (v) => labels[v] || v
async function loadData() {
  items.value = await getData('/teachers/audit-logs')
}
onMounted(load)
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
