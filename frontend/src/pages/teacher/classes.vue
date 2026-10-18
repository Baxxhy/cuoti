<template>
  <view class="teacher-page">
    <app-header title="班级与学生" subtitle="仅显示你管理的班级" back />
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
            <text>我的班级</text>
            <text class="card-link" @click="creating = !creating">新建班级</text>
          </view>
          <view v-if="creating">
            <view class="field">
              <text class="field-label">班级名称</text>
              <input v-model="form.name" placeholder="例如：初二（3）班" />
            </view>
            <view class="field">
              <text class="field-label">年级</text>
              <input v-model="form.grade" placeholder="初二" />
            </view>
            <view class="teacher-actions">
              <button class="primary" :disabled="busy" @click="create">创建</button>
            </view>
          </view>
          <view
            v-for="item in classes"
            :key="item.id"
            class="teacher-row"
            @click="go(`/pages/teacher/class-detail?id=${item.id}`)"
          >
            <view class="row-main">
              <text class="row-title">{{ item.name }}</text>
              <text class="row-meta">
                {{ item.grade || '未设置年级' }} · {{ item.student_count }} 人
              </text>
            </view>
            <uni-icons type="right" size="24" color="#98a2b3" />
          </view>
          <view v-if="!classes.length" class="empty-card">还没有班级</view>
        </view>
      </template>
    </view>
  </view>
</template>
<script setup>
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { getData, postData } from '@/api/index.js'
import { go } from '@/utils/navigation.js'
const classes = ref([]),
  loading = ref(true),
  creating = ref(false),
  form = ref({ name: '', grade: '' })
async function loadData() {
  classes.value = await getData('/teachers/classes')
  loading.value = false
}
async function createData() {
  if (!form.value.name) return
  await postData('/teachers/classes', { ...form.value, reason: '教师创建班级' })
  form.value = { name: '', grade: '' }
  creating.value = false
  await load()
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
const busy = ref(false)
async function create() {
  if (busy.value) return
  busy.value = true
  try {
    await createData()
  } catch {
  } finally {
    busy.value = false
  }
}
</script>
<style lang="scss">
@import './teacher.scss';
</style>
