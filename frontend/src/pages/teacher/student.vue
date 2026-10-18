<template>
  <view class="teacher-page">
    <app-header :title="data?.student?.name || '学生详情'" subtitle="掌握度、错因与教师干预" back />
    <view class="teacher-content">
      <state-panel
        v-if="loading || error || !data"
        :state="error ? 'error' : 'loading'"
        :message="error"
        @retry="load"
      />
      <template v-else>
        <view class="teacher-grid student-report-metrics">
          <view class="metric-card">
            <text class="metric-value">{{ data.summary.questions }}</text>
            <text class="metric-label">错题记录</text>
          </view>
          <view class="metric-card">
            <text class="metric-value">{{ data.summary.completed_sessions }}</text>
            <text class="metric-label">完成学习</text>
          </view>
          <view class="metric-card">
            <text class="metric-value">{{ data.summary.review_records }}</text>
            <text class="metric-label">复习记录</text>
          </view>
        </view>
        <view class="teacher-card">
          <view class="card-heading">
            <text>学习计划</text>
            <text
              class="card-link"
              @click="go(`/pages/teacher/plans?student_id=${data.student.id}&class_id=${classId}`)"
            >
              查看与调整
            </text>
          </view>
          <text class="evidence-text">{{ data.suggestion }}</text>
        </view>
        <view class="two-column student-report-details">
          <view class="teacher-card">
            <view class="card-heading"><text>知识掌握估计</text></view>
            <view v-for="item in mastery" :key="item.id" class="teacher-row">
              <view class="row-main">
                <text class="row-title">{{ item.knowledge_point }}</text>
                <text class="row-meta">
                  {{ item.subject }} · {{ Math.round(item.mastery_score * 100) }}% ·
                  {{ item.evidence_count }} 条学习证据
                </text>
              </view>
            </view>
            <text v-if="!mastery.length" class="muted">暂无掌握证据</text>
          </view>
          <view class="teacher-card">
            <view class="card-heading"><text>需关注的错因</text></view>
            <view v-for="item in misconceptions" :key="item.id" class="teacher-row">
              <view class="row-main">
                <text class="row-title">{{ item.label }}</text>
                <text class="row-meta">
                  {{ item.subject }} · 记录估计 {{ Math.round(item.probability * 100) }}% ·
                  {{ item.evidence_count }} 条学习证据
                </text>
              </view>
            </view>
            <text v-if="!misconceptions.length" class="muted">暂无明确的待处理错因</text>
          </view>
        </view>
        <view class="teacher-card">
          <view class="card-heading"><text>近期认知更新</text></view>
          <view v-for="item in data.recent_updates" :key="item.id" class="teacher-row">
            <view class="row-main">
              <text class="row-title">
                {{
                  item.entity_type === 'misconception'
                    ? reportCauseLabel(item.entity_key) || '错因待核对'
                    : item.entity_key
                }}
              </text>
              <text class="row-meta">
                {{ Math.round(item.old_value * 100) }}% → {{ Math.round(item.new_value * 100) }}% ·
                {{ item.reason }}
              </text>
            </view>
          </view>
        </view>
      </template>
    </view>
  </view>
</template>
<script setup>
import { computed, ref } from 'vue'
import { onLoad, onShow, onHide, onUnload } from '@dcloudio/uni-app'
import { getData } from '@/api/index.js'
import { go } from '@/utils/navigation.js'
import { reportCauses, reportCauseLabel, reportMastery } from '@/utils/report.js'
const data = ref(null),
  classId = ref('')
const mastery = computed(() => reportMastery(data.value?.mastery || []))
const misconceptions = computed(() => reportCauses(data.value?.misconceptions || []))
let id = '',
  generation = 0
onLoad((q) => {
  id = q.id
  classId.value = q.class_id || ''
})
const error = ref(''),
  loading = ref(true)
async function load() {
  const current = ++generation
  data.value = null
  loading.value = true
  error.value = ''
  try {
    const result = await getData(`/teachers/students/${id}/report`)
    if (current === generation) data.value = result
  } catch (err) {
    if (current === generation) error.value = err.message || '暂时无法加载，请重试'
  } finally {
    if (current === generation) loading.value = false
  }
}
function clear() {
  generation++
  data.value = null
}
onShow(load)
onHide(clear)
onUnload(clear)
</script>
<style lang="scss">
@import './teacher.scss';
.teacher-page .student-report-metrics {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}
.teacher-page .student-report-details {
  grid-template-columns: minmax(0, 1fr);
}
@media (min-width: 768px) {
  .teacher-page .student-report-details {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
