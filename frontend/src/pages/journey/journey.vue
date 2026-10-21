<template>
  <view class="page journey-page">
    <app-header title="学习记录" back />
    <view class="page-content">
      <state-panel
        v-if="!journey"
        :state="!id || error ? 'error' : 'loading'"
        :message="!id ? '请先选择一道错题' : undefined"
        :retry-text="!id ? '选择错题' : '重新加载'"
        @retry="id ? load() : go('/pages/problem/list')"
      />
      <template v-else>
        <view class="overview">
          <text class="subject-label">{{ journey.subject }}</text>
          <math-text class="question-copy" :text="journey.question_text" />
          <view class="evidence-labels">
            <text>{{ journey.verification.verified ? '参考答案已校验' : '参考答案待核对' }}</text>
            <text>
              {{ journey.verification.diagnosis_confirmed ? '错因已核对' : '错因待核对' }}
            </text>
          </view>
        </view>
        <view class="next-card">
          <text class="next-heading">下一步</text>
          <button role="button" class="primary-btn" @click="go(journey.next_action.url)">
            {{ journey.next_action.label }}
          </button>
        </view>
        <view v-if="journey.learning_tasks?.items?.length" class="task-records">
          <text class="next-heading">订正进度</text>
          <math-text class="summary" :text="taskSummary" inline />
          <button
            class="record-action"
            @click="go(`/pages/task/task?id=${journey.learning_tasks.items[0].id}`)"
            role="button"
            tabindex="0"
            @keydown.enter.prevent="go(`/pages/task/task?id=${journey.learning_tasks.items[0].id}`)"
          >
            查看最近一次过程
          </button>
          <button
            v-if="journey.self_checks?.length"
            class="record-action"
            :aria-expanded="showNotes"
            @click="showNotes = !showNotes"
            role="button"
            tabindex="0"
            @keydown.enter.prevent="showNotes = !showNotes"
          >
            自检要点（{{ journey.self_checks.length }}） · {{ showNotes ? '收起' : '展开' }}
          </button>
          <view v-if="showNotes" class="self-check-list">
            <view v-for="note in journey.self_checks" :key="note.id" class="self-check-item">
              <math-text :text="note.text" />
              <text class="muted note">
                {{
                  note.source_current
                    ? '自己确认的提醒，不作为掌握证明'
                    : '原题已更新，仅作历史提醒'
                }}
              </text>
              <button
                class="record-action"
                @click="go(`/pages/task/task?id=${note.task_id}`)"
                role="button"
                tabindex="0"
                @keydown.enter.prevent="go(`/pages/task/task?id=${note.task_id}`)"
              >
                查看或修改要点
              </button>
            </view>
          </view>
        </view>
        <view class="section-title"><text>学习进度</text></view>
        <view class="stage-list">
          <view
            v-for="(stage, index) in journey.stages"
            :key="stage.key"
            class="stage-row"
            :class="{ done: stage.completed }"
          >
            <view class="stage-index">
              <uni-icons
                aria-hidden="true"
                v-if="stage.completed"
                type="checkmarkempty"
                size="18"
                color="var(--color-primary)"
              />
              <template v-else>{{ index + 1 }}</template>
            </view>
            <view class="stage-copy">
              <text>{{ stageTitle(stage) }}</text>
              <small v-if="stage.completed"><math-text :text="stage.detail" inline /></small>
            </view>
            <text class="stage-status">{{ stage.completed ? '已完成' : '待完成' }}</text>
          </view>
        </view>

        <view class="evidence-stats">
          <view>
            <b>{{ journey.practice.correct }} / {{ journey.practice.verified_attempts }}</b>
            <text>练习答对 / 已判定</text>
          </view>
          <view>
            <b>{{ journey.review.completed }}</b>
            <text>已完成复习</text>
          </view>
        </view>
        <text v-if="journey.practice.pending" class="muted note">
          {{ journey.practice.pending }} 次练习待核对，未计入正确率。
        </text>
        <text v-if="journey.review.next_due_at" class="muted note">
          下次复习：{{ formatDate(journey.review.next_due_at) }}
        </text>
        <view class="section-title">
          <text>学习记录</text>
          <text class="muted">最近 30 条</text>
        </view>
        <view class="timeline">
          <view v-for="event in journey.events" :key="event.id" class="event-row">
            <view class="event-dot" />
            <view>
              <view class="event-title">
                <b><math-text :text="event.title" inline /></b>
                <small>{{ formatDate(event.time) }}</small>
              </view>
              <math-text class="event-detail" :text="event.detail" />
            </view>
          </view>
        </view>
        <text class="muted note">
          统计基于这道题最近
          {{ journey.history_limit }}
          条记录。
        </text>
        <view class="summary-actions">
          <button role="button" @click="copySummary">复制学习摘要</button>
          <button role="button" @click="go(`/pages/detail/detail?id=${id}`)">回到错题详情</button>
        </view>
      </template>
    </view>
  </view>
</template>

<script setup>
import MathText from '@/components/math-text/math-text.vue'
import { computed, ref } from 'vue'
import { onLoad, onShow } from '@dcloudio/uni-app'
import { getData } from '@/api/index.js'
import { go } from '@/utils/navigation.js'
const id = ref(''),
  journey = ref(null),
  error = ref(false)
const showNotes = ref(false)
const taskSummary = computed(() => {
  const progress = journey.value?.learning_tasks
  if (progress?.near_transfer) return '变式练习已完成，等待复习。'
  if (progress?.original_independent) return '原题已完成，可继续练习类似题。'
  if (progress?.repair_verified) return '错处已订正，接着重新作答。'
  return '订正尚未完成。'
})
let loading = false
async function load() {
  if (!id.value) return
  if (!id.value || loading) return
  loading = true
  error.value = false
  try {
    journey.value = await getData(`/questions/${id.value}/journey`)
  } catch {
    error.value = true
    journey.value = null
  } finally {
    loading = false
  }
}
function stageTitle(stage) {
  return (
    {
      confirmed: '核对题目',
      diagnosed: '找到错因',
      understanding: '理解检查',
      transfer: '类似题检验',
      review: '后续复习',
    }[stage.key] || stage.label
  )
}
function formatDate(value) {
  if (!value) return ''
  return new Date(value).toLocaleString('zh-CN', {
    timeZone: 'Asia/Shanghai',
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}
function copySummary() {
  const data = journey.value
  const text = [
    '错题帮 · 学习摘要',
    data.question_text,
    data.summary,
    ...data.stages.map(
      (stage) =>
        `${stage.completed ? '已完成' : '未完成'} ${stageTitle(stage)}${stage.completed ? '：' + stage.detail : ''}`,
    ),
    `下一步：${data.next_action.label}`,
    `生成时间：${formatDate(data.generated_at)}`,
  ].join('\n')
  uni.setClipboardData({ data: text })
}
onLoad((query) => {
  id.value = query.id || ''
  load()
})
onShow(() => {
  if (journey.value) load()
})
</script>

<style scoped lang="scss">
.journey-page {
  padding-bottom: 20px;
}
.task-records {
  padding: 16px 0;
  border-bottom: 1px solid var(--color-border);
}
.record-action {
  display: block;
  margin: 0;
  padding: 12px 0;
  min-height: 48px;
  background: transparent;
  color: var(--color-primary);
  text-align: left;
  font-size: 14px;
}
.self-check-item {
  font-size: 16px;
  line-height: 1.6;
  padding: 16px 0;
  border-top: 1px solid var(--color-border);
}
.overview {
  padding: 2px 0 13px;
  border-bottom: 0.5px solid var(--color-border);
}
.subject-label {
  font-size: 12px;
  color: var(--color-text-secondary);
}
.question-copy {
  display: block;
  margin-top: 6px;
  font-size: 15.5px;
  line-height: 1.8;
}
.summary {
  display: block;
  margin-top: 6px;
  color: var(--color-text-secondary);
  font-size: 13px;
  line-height: 1.75;
}
.evidence-labels {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 12px;
  margin-top: 9px;
}
.evidence-labels text {
  color: var(--color-text-secondary);
  font-size: 12px;
  line-height: 1.6;
}
.section-title {
  margin-top: 15px;
  font-size: 14.5px;
}
.stage-list {
  padding: 0;
}
.stage-row {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 11px 0;
  border-bottom: 0.5px solid var(--color-border);
}
.stage-index {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
  width: 22px;
  height: 22px;
  border: 0.5px solid var(--color-border);
  border-radius: 50%;
  background: #fff;
  color: var(--color-text-tertiary);
  font-size: 12px;
}
.done .stage-index {
  border-color: var(--color-primary);
}
.stage-copy {
  flex: 1;
  min-width: 0;
}
.stage-copy text,
.stage-copy small {
  display: block;
}
.stage-copy text {
  font-size: 14px;
  font-weight: 500;
}
.stage-copy small {
  margin-top: 3px;
  color: var(--color-text-secondary);
  font-size: 12px;
  line-height: 1.6;
}
.stage-status {
  flex: none;
  color: var(--color-text-tertiary);
  font-size: 12px;
}
.done .stage-status {
  color: var(--color-primary);
}
.next-card {
  padding: 14px 0;
  border-bottom: 0.5px solid var(--color-border);
}
.next-heading {
  font-size: 14px;
  font-weight: 600;
}
.next-card .primary-btn {
  margin-top: 11px;
}
.evidence-stats {
  display: grid;
  grid-template-columns: 1fr 1fr;
  margin-top: 13px;
}
.evidence-stats > view {
  padding: 5px 10px 5px 0;
}
.evidence-stats > view + view {
  padding-left: 12px;
  border-left: 0.5px solid var(--color-border);
}
.evidence-stats b,
.evidence-stats text {
  display: block;
}
.evidence-stats b {
  font-size: 18px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.evidence-stats text {
  margin-top: 4px;
  color: var(--color-text-secondary);
  font-size: 12px;
}
.note {
  display: block;
  margin: 8px 0;
  color: var(--color-text-secondary);
  font-size: 12px;
  line-height: 1.7;
}
.event-row {
  display: grid;
  grid-template-columns: 6px 1fr;
  gap: 10px;
  padding: 2px 0 13px;
}
.event-dot {
  width: 4px;
  height: 4px;
  margin-top: 8px;
  border-radius: 50%;
  background: var(--color-text-tertiary);
}
.event-title {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 6px;
}
.event-title b {
  font-size: 13px;
  font-weight: 500;
}
.event-title small {
  flex: none;
  color: var(--color-text-tertiary);
  font-size: 12px;
}
.event-detail {
  display: block;
  margin-top: 4px;
  color: var(--color-text-secondary);
  font-size: 12px;
  line-height: 1.65;
}
.summary-actions {
  display: flex;
  gap: 10px;
  border-top: 0.5px solid var(--color-border);
}
.summary-actions button {
  flex: 1;
  min-height: 44px;
  margin: 0;
  padding: 7px 0;
  background: transparent;
  color: var(--color-primary);
  font-size: 12px;
}
.summary-actions button::after {
  border: 0;
}
</style>
