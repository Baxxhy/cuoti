<template>
  <view class="page assignment-page">
    <app-header title="我的作业" subtitle="选一项，写完提交" back />
    <view class="page-content">
      <state-panel
        v-if="loading || error"
        :state="error ? 'error' : 'loading'"
        :message="error"
        @retry="load"
      />
      <template v-else>
        <view v-if="items.length" class="assignment-summary">
          <text>待完成 {{ pendingCount }} 项</text>
          <text>共 {{ items.length }} 项</text>
        </view>
        <view v-for="item in items" :key="item.student_assignment.id" class="assignment-card">
          <button
            class="assignment-header"
            :aria-expanded="selected === item.student_assignment.id"
            :disabled="busy !== '' || Object.values(uploading).some(Boolean)"
            @click="
              selected = selected === item.student_assignment.id ? '' : item.student_assignment.id
            "
          >
            <view class="assignment-meta">
              <text>{{ item.question.subject }} · {{ item.question.question_type }}</text>
              <text>{{ statusText(item.student_assignment.status) }}</text>
            </view>
            <text class="assignment-title">{{ item.assignment.title }}</text>
            <text class="assignment-toggle">
              {{ selected === item.student_assignment.id ? '收起' : '打开作业' }}
            </text>
          </button>
          <view v-show="selected === item.student_assignment.id" class="assignment-body">
            <math-text class="assignment-question" :text="item.question.question_text" />
            <view v-for="option in normalizeOptions(item.question.options)" :key="option.label">
              <math-text :text="`${option.label}. ${option.text}`" />
            </view>
            <text class="assignment-due">
              截止：{{
                item.assignment.due_at
                  ? new Date(item.assignment.due_at).toLocaleString('zh-CN', { hour12: false })
                  : '未设置'
              }}
            </text>
            <template v-if="canAnswer(item)">
              <text v-if="item.require_handwriting" class="handwriting-required">
                本题需要上传手写作答照片
              </text>
              <written-answer
                :key="`${item.student_assignment.id}:${item.student_assignment.latest_attempt_id || ''}`"
                v-model="answers[item.student_assignment.id]"
                upload-url="/answers/handwriting"
                :upload-data="{
                  context_type: 'assignment',
                  context_id: item.student_assignment.id,
                }"
                @handwriting-change="photos[item.student_assignment.id] = $event"
                @uploading-change="uploading[item.student_assignment.id] = $event"
              />
              <button
                class="primary-btn"
                :disabled="
                  busy !== '' ||
                  uploading[item.student_assignment.id] ||
                  !answers[item.student_assignment.id]?.trim() ||
                  (item.require_handwriting && !photos[item.student_assignment.id]?.image_url)
                "
                @click="submit(item.student_assignment.id)"
              >
                {{
                  busy === item.student_assignment.id
                    ? '提交中…'
                    : item.student_assignment.status === 'completed'
                      ? '再次提交'
                      : '提交作答'
                }}
              </button>
            </template>
            <view v-else class="assignment-result">
              <text>{{ resultText(item) }}</text>
            </view>
            <view v-if="item.teacher_feedback" class="teacher-feedback">
              <b>教师反馈 · {{ conclusionText(item.teacher_feedback.conclusion) }}</b>
              <text v-if="item.teacher_feedback.score != null">
                得分：{{ item.teacher_feedback.score }}
              </text>
              <math-text
                v-if="item.teacher_feedback.first_key_error"
                :text="`关键错误：${item.teacher_feedback.first_key_error}`"
              />
              <math-text
                v-if="item.teacher_feedback.student_hint"
                :text="item.teacher_feedback.student_hint"
              />
              <text v-if="item.teacher_feedback.next_task">
                下一步：{{ item.teacher_feedback.next_task }}
              </text>
            </view>
            <view v-if="item.grading_feedback" class="grading-feedback">
              <math-text :text="item.grading_feedback" />
            </view>
          </view>
        </view>
        <view v-if="!items.length" class="empty">还没有作业，老师布置后会显示在这里</view>
      </template>
    </view>
  </view>
</template>
<script setup>
import WrittenAnswer from '@/components/written-answer/written-answer.vue'
import { computed, reactive, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { normalizeOptions } from '@/utils/question.js'
import { getData, postData } from '@/api/index.js'
const items = ref([]),
  loading = ref(true),
  busy = ref(''),
  selected = ref(''),
  answers = reactive({}),
  photos = reactive({}),
  uploading = reactive({})
const pendingCount = computed(
  () => items.value.filter((item) => item.student_assignment.status === 'pending').length,
)
function canAnswer(item) {
  const status = item.student_assignment.status
  return status === 'pending' || (status === 'completed' && item.assignment.settings?.allow_repeat)
}
const statusText = (v) =>
    ({
      pending: '待完成',
      review_pending: '教师核对中',
      completed: '已完成',
      question_issue: '题目核对中',
    })[v] || v,
  resultText = (item) =>
    item.student_assignment.status === 'question_issue'
      ? '题目正在核对，暂不需要作答。'
      : item.student_assignment.status === 'review_pending'
        ? '作答已提交，等待教师核对。'
        : item.teacher_feedback
          ? '作答已完成，可查看教师反馈。'
          : '作答已完成。',
  conclusionText = (v) =>
    ({
      confirmed_correct: '确认正确',
      confirmed_incorrect: '确认错误',
      partially_correct: '部分正确',
      resubmit: '请修改后重新提交',
      question_issue: '题目需要核对',
    })[v] || '已核对'
async function loadData() {
  items.value = await getData('/students/assignments')
  if (!items.value.some((item) => item.student_assignment.id === selected.value))
    selected.value =
      (items.value.find((item) => item.student_assignment.status === 'pending') || items.value[0])
        ?.student_assignment.id || ''
  for (const item of items.value) {
    const link = item.student_assignment
    if (canAnswer(item) && item.latest_attempt && !answers[link.id])
      answers[link.id] = item.latest_attempt.answer || ''
  }
  loading.value = false
}
async function submit(id) {
  if (busy.value || uploading[id] || !answers[id]?.trim()) return
  busy.value = id
  try {
    const result = await postData(`/students/assignments/${id}/attempts`, {
      answer: answers[id],
      steps: answers[id].split('\n').filter(Boolean),
      handwriting_image_url: photos[id]?.image_url || '',
      handwriting_recognition: photos[id]?.recognition || null,
    })
    uni.showToast({
      title: result.entered_review_queue ? '已提交教师核对' : '作答已完成',
      icon: 'none',
    })
    delete photos[id]
    await load()
  } catch (err) {
    // The request layer shows the reason. Keep the answer available for retry.
  } finally {
    busy.value = ''
  }
}
onShow(load)
const error = ref('')
async function load() {
  loading.value = items.value.length === 0
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
.assignment-page {
  min-height: 100vh;
  background: var(--color-bg);
}
.assignment-summary {
  display: flex;
  justify-content: space-between;
  gap: 20rpx;
  color: var(--color-text-secondary);
  font-size: 28rpx;
  margin: 8rpx 0 24rpx;
}
.assignment-header {
  display: block;
  width: 100%;
  padding: 28rpx;
  margin: 0;
  text-align: left;
  background: var(--color-surface);
  border-radius: 22rpx;
  line-height: 1.5;
}
.assignment-header::after {
  border: none;
}
.assignment-header[aria-expanded='true'] {
  background: var(--color-primary-soft);
}
.assignment-toggle {
  display: block;
  font-size: 26rpx;
  color: var(--color-primary);
  margin-top: 12rpx;
}
.assignment-body {
  padding: 0 28rpx 28rpx;
}
.assignment-card {
  margin: 22rpx 0;
  overflow: hidden;
  border: 1rpx solid var(--color-border);
  border-radius: 22rpx;
  background: #fff;
}
.assignment-meta {
  display: flex;
  justify-content: space-between;
  gap: 20rpx;
  color: var(--color-primary-hover);
  font-size: 26rpx;
}
.assignment-title {
  display: block;
  margin-top: 18rpx;
  color: var(--color-text-primary);
  font-size: 30rpx;
  font-weight: 650;
}
.assignment-question {
  display: block;
  margin-top: 15rpx;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
  color: var(--color-text-primary);
  font-size: 32rpx;
  line-height: 1.75;
}
.assignment-due {
  display: block;
  margin-top: 12rpx;
  color: var(--color-text-secondary);
  font-size: 26rpx;
}
.handwriting-required {
  display: block;
  margin-top: 18rpx;
  color: var(--color-text-secondary);
  font-size: 24rpx;
}
.assignment-result {
  margin-top: 20rpx;
  padding: 20rpx;
  border-radius: 14rpx;
  background: var(--color-primary-soft);
  color: var(--color-primary-hover);
  font-size: 24rpx;
  line-height: 1.6;
}
.teacher-feedback,
.grading-feedback {
  margin-top: 16rpx;
  padding: 20rpx;
  border: 1rpx solid var(--color-border);
  border-radius: 14rpx;
  background: var(--color-surface-subtle);
  font-size: 25rpx;
  line-height: 1.65;
}
.teacher-feedback b,
.teacher-feedback text {
  display: block;
  margin-bottom: 8rpx;
}
.empty {
  padding: 100rpx 20rpx;
  text-align: center;
  color: var(--color-text-tertiary);
  font-size: 25rpx;
}
</style>
