<template>
  <view class="teacher-page">
    <app-header title="待核对队列" subtitle="未确认前不更新学生学习状态" back />
    <view class="teacher-content">
      <view class="teacher-card">
        <view class="section-tabs">
          <text :class="{ active: filter === '' }" @click="setFilter('')">全部</text>
          <text
            :class="{ active: filter === 'probably_correct' }"
            @click="setFilter('probably_correct')"
          >
            可能正确
          </text>
          <text
            :class="{ active: filter === 'review_required' }"
            @click="setFilter('review_required')"
          >
            需要核对
          </text>
        </view>
        <state-panel
          v-if="loading || error"
          :state="error ? 'error' : 'loading'"
          :message="error"
          @retry="load"
        />
        <template v-else>
          <view
            v-for="item in items"
            :key="item.id"
            class="teacher-row"
            @click="go(`/pages/teacher/review-detail?id=${item.id}`)"
          >
            <view class="row-main">
              <text class="row-title">{{ item.student_name }} · {{ item.question_title }}</text>
              <text class="row-meta">{{ item.question_summary }}</text>
              <text class="row-meta">
                作答：{{ item.student_answer || '未识别' }} · 置信度
                {{ Math.round(item.confidence * 100) }}% · 等待 {{ item.waiting_minutes }} 分钟
              </text>
              <text class="row-meta">原因：{{ reasonText(item.reason_codes) }}</text>
            </view>
            <text class="tag" :class="{ warn: item.verdict === 'review_required' }">
              {{ verdictText(item.verdict) }}
            </text>
          </view>
          <view v-if="!items.length" class="empty-card">当前没有等待核对的作答</view>
        </template>
      </view>
    </view>
  </view>
</template>
<script setup>
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { getData } from '@/api/index.js'
import { go } from '@/utils/navigation.js'
const items = ref([]),
  loading = ref(true),
  filter = ref('')
const labels = {
  probably_correct: '可能正确',
  review_required: '需要核对',
  rule_llm_conflict: '规则与模型冲突',
  low_ocr_confidence: 'OCR 置信度低',
  incomplete_reference: '答案或步骤不完整',
  teacher_required: '教师指定复核',
  auto_grade_disabled: '禁止自动判题',
}
const verdictText = (v) => labels[v] || v
const reasonText = (v) => (v || []).map((x) => labels[x] || x).join('、')
function setFilter(v) {
  filter.value = v
  load()
}
onShow(load)
const error = ref('')
let requestId = 0
async function load() {
  const current = ++requestId
  loading.value = true
  error.value = ''
  try {
    const result = await getData(
      `/teachers/reviews${filter.value ? `?verdict=${filter.value}` : ''}`,
    )
    if (current === requestId) items.value = result
  } catch (err) {
    if (current === requestId) error.value = err.message || '暂时无法加载，请重试'
  } finally {
    if (current === requestId) loading.value = false
  }
}
</script>
<style lang="scss">
@import './teacher.scss';
</style>
