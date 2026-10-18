<template>
  <view class="page repair-page">
    <app-header title="本题修复路线" back :back-fallback="`/pages/detail/detail?id=${id}`" />
    <view class="page-content">
      <state-panel
        v-if="loading || error"
        :state="error ? 'error' : 'loading'"
        :message="error"
        @retry="load"
      />
      <template v-else-if="item && journey">
        <view class="editorial-heading">
          <text class="eyebrow">{{ item.subject }} · 依据本题实际学习记录</text>
          <text class="editorial-title">这道题，逐步修复。</text>
          <math-text
            class="editorial-description"
            :text="item.diagnosis?.root_misconception || '先核对题目与自己的作答，再逐步验证。'"
          />
        </view>
        <text v-if="notice" class="account-notice" role="alert">{{ notice }}</text>
        <view class="repair-timeline">
          <view
            v-for="(step, i) in route"
            :key="step.key"
            class="repair-step"
            :class="{ recommended: step.recommended }"
          >
            <text class="repair-number">{{ String(i + 1).padStart(2, '0') }}</text>
            <view class="repair-copy">
              <view class="repair-step-heading">
                <text>{{ step.title }}</text>
                <small>{{ step.recommended ? '建议先做 · ' : '' }}{{ step.state }}</small>
              </view>
              <math-text class="editorial-description" :text="step.detail" />
              <button
                role="button"
                tabindex="0"
                class="route-action"
                :aria-label="actionLabel(step)"
                :disabled="busy"
                @keydown.enter.prevent="openStep(step)"
                @keydown.space.prevent
                @keyup.space.prevent="openStep(step)"
                @click="openStep(step)"
              >
                {{ actionLabel(step) }}
                <uni-icons aria-hidden="true" type="right" size="18" />
              </button>
              <button
                aria-label="试一道变式题"
                role="button"
                tabindex="0"
                v-if="step.key === 'practice'"
                class="route-action secondary-route"
                @keydown.enter.prevent="go(`/pages/practice/practice?id=${id}&mode=variation`)"
                @keydown.space.prevent
                @keyup.space.prevent="go(`/pages/practice/practice?id=${id}&mode=variation`)"
                @click="go(`/pages/practice/practice?id=${id}&mode=variation`)"
              >
                试一道变式题
                <uni-icons aria-hidden="true" type="right" size="18" />
              </button>
            </view>
          </view>
        </view>
        <text class="evidence-caption">
          路线来自真实档案，不因浏览页面而标记完成。订正、理解、独立迁移与复习分别记录；一道练习不代表掌握整个知识点。
        </text>
        <button
          aria-label="查看学习证据与历史"
          role="button"
          tabindex="0"
          class="disclosure-link"
          @keydown.enter.prevent="go(`/pages/journey/journey?id=${id}`)"
          @keydown.space.prevent
          @keyup.space.prevent="go(`/pages/journey/journey?id=${id}`)"
          @click="go(`/pages/journey/journey?id=${id}`)"
        >
          查看学习证据与历史
          <uni-icons aria-hidden="true" type="right" size="18" />
        </button>
        <button
          aria-label="返回个人易错地图"
          role="button"
          tabindex="0"
          class="disclosure-link"
          @keydown.enter.prevent="go('/pages/error-map/error-map')"
          @keydown.space.prevent
          @keyup.space.prevent="go('/pages/error-map/error-map')"
          @click="go('/pages/error-map/error-map')"
        >
          返回个人易错地图
          <uni-icons aria-hidden="true" type="right" size="18" />
        </button>
      </template>
    </view>
  </view>
</template>
<script setup>
import { computed, ref } from 'vue'
import { onLoad, onShow, onHide, onUnload } from '@dcloudio/uni-app'
import { getData } from '@/api/index.js'
import { go } from '@/utils/navigation.js'
import { requestLearningTask } from '@/utils/task-entry.js'
import { repairRoute } from '@/utils/repair.js'
const id = ref(''),
  item = ref(null),
  journey = ref(null),
  loading = ref(true),
  error = ref(''),
  busy = ref(false),
  notice = ref('')
let revision = 0
const route = computed(() => (item.value ? repairRoute(item.value, journey.value) : []))
function actionLabel(step) {
  return step.key === 'learn'
    ? busy.value
      ? '正在准备…'
      : '进入学习任务'
    : step.key === 'practice'
      ? '开始针对练习'
      : step.key === 'review'
        ? '查看复习安排'
        : step.key === 'knowledge'
          ? '回顾知识'
          : '核对作答'
}
async function load() {
  const version = ++revision
  loading.value = true
  error.value = ''
  notice.value = ''
  try {
    if (!id.value) throw new Error('请从一道错题进入修复路线。')
    const [question, record] = await Promise.all([
      getData(`/questions/${encodeURIComponent(id.value)}`),
      getData(`/questions/${encodeURIComponent(id.value)}/journey`),
    ])
    // The queue remembers its own position. A question-specific route must
    // explicitly choose this question's current plan, rather than that position.
    if (record.review?.due) {
      const plans = await getData('/reviews/today')
      record.review.plan_id = plans.find((plan) => plan.question_id === question.id)?.id || ''
    }
    if (version === revision) {
      item.value = question
      journey.value = record
    }
  } catch (err) {
    if (version === revision) error.value = err.message || '修复路线暂时无法读取'
  } finally {
    if (version === revision) loading.value = false
  }
}
async function openStep(step) {
  if (busy.value) return
  if (step.key !== 'learn') return go(step.url)
  if (!item.value?.confirmed || !item.value?.analysis)
    return go(`/pages/detail/detail?id=${id.value}`)
  const version = revision
  busy.value = true
  notice.value = ''
  try {
    const task = await requestLearningTask(id.value)
    if (version === revision) go(`/pages/task/task?id=${task.id}`)
  } catch (err) {
    if (version === revision) notice.value = err.message || '任务暂时无法开始，请重试'
  } finally {
    if (version === revision) busy.value = false
  }
}
function clear() {
  revision++
  item.value = null
  journey.value = null
  busy.value = false
}
onLoad((query) => {
  id.value = query.id || ''
})
onShow(load)
onHide(clear)
onUnload(clear)
</script>
<style scoped lang="scss">
.repair-timeline {
  margin: 32px 0 24px;
}
.repair-step {
  display: grid;
  grid-template-columns: 52px minmax(0, 1fr);
  position: relative;
}
.repair-number {
  padding-top: 20px;
  font-size: 20px;
  font-weight: 500;
  color: var(--color-primary);
  font-variant-numeric: tabular-nums;
}
.repair-copy {
  padding: 16px 0 12px 20px;
  border-left: 1px solid var(--color-primary-border);
  border-top: 1px solid var(--color-border);
}
.repair-step:first-child .repair-copy {
  border-top: 2px solid var(--color-text-primary);
}
.repair-step.recommended .repair-copy {
  border-left: 3px solid var(--color-primary);
  padding-left: 18px;
}
.repair-step.recommended .repair-step-heading small {
  color: var(--color-primary);
}
.repair-step-heading {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 8px 16px;
  margin-bottom: 8px;
}
.repair-step-heading > text {
  font-size: 18px;
  font-weight: 600;
}
.repair-step-heading small {
  font-size: 12px;
  color: var(--color-text-secondary);
}
.route-action {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  min-height: 44px;
  margin: 8px 16px 0 0;
  padding: 10px 0;
  font-size: 14px;
  text-align: left;
  background: transparent;
  color: var(--color-primary);
}
.secondary-route {
  color: var(--color-text-secondary);
}
.repair-page .evidence-caption {
  display: block;
  margin: 24px 0;
}
</style>
