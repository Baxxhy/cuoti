<template>
  <view class="teacher-page">
    <app-header title="学习计划管理" subtitle="调整会立即反映到学生复习页" back />
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
            <text class="row-title">{{ item.reason }}</text>
            <text class="row-meta">
              截止：{{ formatDate(item.due_at) }} · {{ statusText(item.status) }}
            </text>
          </view>
          <view class="teacher-actions"><button @click="edit(item)">调整</button></view>
        </view>
        <view v-if="!items.length" class="empty-card">暂无学习计划</view>
      </view>
      <view v-if="current" class="teacher-card">
        <view class="card-heading"><text>调整计划</text></view>
        <view class="field">
          <text class="field-label">任务说明</text>
          <input v-model="form.task_reason" />
        </view>
        <view class="field">
          <text class="field-label">截止时间</text>
          <date-time-input v-model="form.due_at" />
        </view>
        <view class="section-tabs">
          <text
            v-for="s in statuses"
            :key="s.value"
            :class="{ active: form.status === s.value }"
            @click="form.status = s.value"
          >
            {{ s.label }}
          </text>
        </view>
        <view class="field">
          <text class="field-label">修改原因（必填）</text>
          <textarea v-model="form.reason" />
        </view>
        <view class="teacher-actions">
          <button class="primary" :disabled="busy" @click="save">保存调整</button>
        </view>
      </view>
    </view>
  </view>
</template>
<script setup>
import DateTimeInput from '@/components/date-time-input/date-time-input.vue'
import { reactive, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { getData, patchData } from '@/api/index.js'
const items = ref([]),
  loading = ref(true),
  current = ref(null)
let studentId = '',
  classId = ''
const form = reactive({ task_reason: '', due_at: '', status: 'pending', reason: '' }),
  statuses = [
    { label: '进行中', value: 'pending' },
    { label: '暂停', value: 'paused' },
    { label: '取消', value: 'cancelled' },
  ]
const formatDate = (v) => (v ? new Date(v).toLocaleString('zh-CN', { hour12: false }) : '未设置')
const statusText = (v) =>
  ({ pending: '进行中', paused: '暂停', cancelled: '取消', completed: '完成' })[v] || v
async function loadData() {
  items.value = await getData(`/teachers/students/${studentId}/plans?class_id=${classId}`)
  loading.value = false
}
function edit(item) {
  current.value = item
  Object.assign(form, {
    task_reason: item.reason,
    due_at: item.due_at,
    status: item.status,
    reason: '',
  })
}
async function saveData() {
  if (form.due_at && !Number.isFinite(Date.parse(form.due_at)))
    return uni.showToast({ title: '截止时间格式不正确', icon: 'none' })
  if (!form.due_at) return uni.showToast({ title: '请选择截止时间', icon: 'none' })
  if (!form.reason) return uni.showToast({ title: '请填写修改原因', icon: 'none' })
  await patchData(`/teachers/plans/${current.value.id}`, { ...form, class_id: classId })
  current.value = null
  await load()
}
onLoad((q) => {
  studentId = q.student_id
  classId = q.class_id
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
async function save() {
  if (busy.value) return
  busy.value = true
  try {
    await saveData()
  } catch {
  } finally {
    busy.value = false
  }
}
</script>
<style lang="scss">
@import './teacher.scss';
</style>
