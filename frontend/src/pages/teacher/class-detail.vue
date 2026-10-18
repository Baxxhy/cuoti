<template>
  <view class="teacher-page">
    <app-header
      :title="data?.name || '班级详情'"
      :subtitle="`${data?.grade || ''} · 真实学习数据聚合`"
      back
    />
    <view class="teacher-content">
      <state-panel
        v-if="loading || error"
        :state="error ? 'error' : 'loading'"
        :message="error"
        @retry="load"
      />
      <template v-else>
        <view class="teacher-card">
          <view class="card-heading">
            <text>学生</text>
            <text class="card-link" @click="adding = !adding">添加学生</text>
          </view>
          <view v-if="adding">
            <view class="field">
              <text class="field-label">学生账号邮箱</text>
              <input v-model="email" placeholder="student@example.com" />
            </view>
            <view class="teacher-actions">
              <button class="primary" :disabled="busy" @click="add">加入班级</button>
            </view>
          </view>
          <view
            v-for="student in data.students"
            :key="student.id"
            class="teacher-row"
            @click="go(`/pages/teacher/student?id=${student.id}&class_id=${data.id}`)"
          >
            <view class="row-main">
              <text class="row-title">{{ student.name }}</text>
              <text class="row-meta">
                掌握 {{ Math.round(student.average_mastery * 100) }}% · 活跃错因
                {{ student.active_misconceptions }} 个
              </text>
            </view>
            <uni-icons type="right" size="24" color="#98a2b3" />
          </view>
          <view v-if="!data.students?.length" class="empty-card">班级中还没有学生</view>
        </view>
      </template>
    </view>
  </view>
</template>
<script setup>
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { getData, postData } from '@/api/index.js'
import { go } from '@/utils/navigation.js'
const data = ref(null),
  loading = ref(true),
  adding = ref(false),
  email = ref('')
let id = ''
async function loadData() {
  data.value = await getData(`/teachers/classes/${id}`)
  loading.value = false
}
async function addData() {
  if (!email.value) return
  await postData(`/teachers/classes/${id}/students`, { email: email.value, reason: '教师添加学生' })
  email.value = ''
  adding.value = false
  await load()
}
onLoad((q) => {
  id = q.id
  load()
})
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
const busy = ref(false)
async function add() {
  if (busy.value) return
  busy.value = true
  try {
    await addData()
  } catch {
  } finally {
    busy.value = false
  }
}
</script>
<style lang="scss">
@import './teacher.scss';
</style>
