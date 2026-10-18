<template>
  <view class="teacher-page">
    <app-header title="题目布置" subtitle="支持整班布置，自动同步学生任务" back />
    <view class="teacher-content">
      <state-panel
        v-if="loading || error"
        :state="error ? 'error' : 'loading'"
        :message="error"
        @retry="load"
      />
      <template v-else>
        <view class="teacher-card">
          <view class="card-heading"><text>新建布置</text></view>
          <view class="field">
            <text class="field-label">任务名称</text>
            <input v-model="form.title" />
          </view>
          <view class="field">
            <text class="field-label">选择班级</text>
            <picker
              :range="classes"
              range-key="name"
              @change="form.class_id = classes[$event.detail.value]?.id"
            >
              <view class="field-box">{{ className || '请选择班级' }}</view>
            </picker>
          </view>
          <view class="field">
            <text class="field-label">选择题目</text>
            <picker
              :range="questions"
              range-key="label"
              @change="form.question_id = questions[$event.detail.value]?.id"
            >
              <view class="field-box">{{ questionName || '请选择题目' }}</view>
            </picker>
          </view>
          <view class="field">
            <text class="field-label">截止时间</text>
            <date-time-input v-model="form.due_at" clearable />
          </view>
          <view class="section-tabs">
            <text
              :class="{ active: settings.allow_repeat }"
              @click="settings.allow_repeat = !settings.allow_repeat"
            >
              允许重复作答
            </text>
            <text
              :class="{ active: settings.allow_auto_grade }"
              @click="settings.allow_auto_grade = !settings.allow_auto_grade"
            >
              允许 AI 判题
            </text>
            <text
              :class="{ active: settings.require_teacher_review }"
              @click="settings.require_teacher_review = !settings.require_teacher_review"
            >
              必须教师批改
            </text>
            <text
              :class="{ active: settings.count_mastery }"
              @click="settings.count_mastery = !settings.count_mastery"
            >
              计入掌握度
            </text>
          </view>
          <view class="teacher-actions">
            <button class="primary" :disabled="busy" @click="create">布置给全班</button>
          </view>
        </view>
        <view class="teacher-card">
          <view class="card-heading"><text>布置记录</text></view>
          <view v-for="item in assignments" :key="item.id" class="teacher-row">
            <view class="row-main">
              <text class="row-title">{{ item.title }}</text>
              <text class="row-meta">
                完成 {{ item.completed_count }} / {{ item.student_count }} · 截止
                {{
                  item.due_at
                    ? new Date(item.due_at).toLocaleString('zh-CN', { hour12: false })
                    : '未设置'
                }}
              </text>
            </view>
            <text class="tag">{{ item.status }}</text>
          </view>
          <view v-if="!assignments.length" class="empty-card">还没有布置记录</view>
        </view>
      </template>
    </view>
  </view>
</template>
<script setup>
import DateTimeInput from '@/components/date-time-input/date-time-input.vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { getData, postData } from '@/api/index.js'
const classes = ref([]),
  questions = ref([]),
  assignments = ref([]),
  form = reactive({ title: '练习任务', class_id: '', question_id: '', due_at: '' }),
  settings = reactive({
    allow_repeat: false,
    allow_auto_grade: true,
    require_teacher_review: false,
    count_mastery: true,
    review_uncertain: true,
  })
const className = computed(() => classes.value.find((x) => x.id === form.class_id)?.name),
  questionName = computed(() => questions.value.find((x) => x.id === form.question_id)?.label)
async function loadData() {
  const [cs, qs, as] = await Promise.all([
    getData('/teachers/classes'),
    getData('/teachers/questions'),
    getData('/teachers/assignments'),
  ])
  classes.value = cs
  questions.value = qs.map((x) => ({ id: x.question.id, label: x.question.title }))
  assignments.value = as
}
async function createData() {
  if (form.due_at && !Number.isFinite(Date.parse(form.due_at)))
    return uni.showToast({ title: '截止时间格式不正确', icon: 'none' })
  if (!form.class_id || !form.question_id)
    return uni.showToast({ title: '请选择班级和题目', icon: 'none' })
  await postData('/teachers/assignments', {
    ...form,
    due_at: form.due_at || null,
    settings: { ...settings },
    reason: '教师布置练习',
  })
  uni.showToast({ title: '已布置', icon: 'success' })
  await load()
}
onMounted(load)
const loading = ref(true),
  error = ref(''),
  busy = ref(false)
async function load() {
  loading.value = true
  error.value = ''
  try {
    await loadData()
  } catch (err) {
    error.value = err.message || '布置记录暂时无法加载，请重试'
  } finally {
    loading.value = false
  }
}
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
