<template>
  <view class="teacher-page">
    <app-header title="题目管理" subtitle="题目与学生错题共用统一数据模型" back />
    <view class="teacher-content">
      <view class="teacher-card">
        <view class="card-heading">
          <text>我的题目</text>
          <text class="card-link" @click="go('/pages/teacher/question-edit')">新增题目</text>
        </view>
        <state-panel
          v-if="loading || error"
          :state="error ? 'error' : 'loading'"
          :message="error"
          @retry="load"
        />
        <template v-else>
          <view v-for="item in items" :key="item.question.id" class="teacher-row">
            <view class="row-main">
              <text class="row-title">{{ item.question.title }}</text>
              <text class="row-meta">
                {{ item.question.subject }} · {{ item.question.grade || '未设年级' }} ·
                {{ item.question.question_type }} ·
                {{ item.teacher_question.difficulty || '未设难度' }}
              </text>
              <text class="row-meta">{{ item.question.question_text }}</text>
            </view>
            <text class="tag" :class="{ warn: !item.teacher_question.allow_auto_grade }">
              {{ item.teacher_question.allow_auto_grade ? '可自动判题' : '教师判题' }}
            </text>
          </view>
          <view v-if="!items.length" class="empty-card">还没有教师题目</view>
        </template>
      </view>
    </view>
  </view>
</template>
<script setup>
import { onMounted, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { getData } from '@/api/index.js'
import { go } from '@/utils/navigation.js'
const items = ref([]),
  loading = ref(true)
async function loadData() {
  items.value = await getData('/teachers/questions')
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
