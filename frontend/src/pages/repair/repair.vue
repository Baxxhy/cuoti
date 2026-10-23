<template>
  <view class="page repair-page">
    <app-header
      title="学习安排"
      back
      :back-fallback="id ? `/pages/detail/detail?id=${id}` : '/pages/problem/list'"
    />
    <view class="page-content">
      <state-panel
        v-if="loading || error"
        :state="error ? 'error' : 'loading'"
        :message="error"
        :retry-text="!id ? '选择错题' : '重新加载'"
        @retry="id ? load() : go('/pages/problem/list')"
      />
      <template v-else-if="item && journey">
        <view class="editorial-heading">
          <text class="eyebrow">{{ item.subject }}</text>
          <math-text class="editorial-description" :text="item.question_text || '这道错题'" />
        </view>
        <text v-if="notice" class="account-notice" role="alert">{{ notice }}</text>
        <view class="repair-timeline">
          <view
            v-for="(step, i) in route"
            :key="step.key"
            class="repair-step"
            :class="{ recommended: step.recommended }"
          >
            <text class="repair-number">{{ i + 1 }}</text>
            <view class="repair-copy">
              <view class="repair-step-heading">
                <math-text :text="step.title" inline />
                <small
                  v-if="step.recommended || !['可回看', '可核对', '查看安排'].includes(step.state)"
                >
                  {{ step.recommended ? '建议先做 · ' : '' }}{{ step.state }}
                </small>
              </view>
              <math-text
                v-if="step.key === 'knowledge' && item.diagnosis?.missing_prerequisites?.length"
                class="editorial-description"
                :text="step.detail"
              />
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
                <uni-icons
                  aria-hidden="true"
                  type="right"
                  size="18"
                  :color="step.recommended ? '#fff' : 'var(--color-primary)'"
                />
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
        <button
          aria-label="查看学习记录"
          role="button"
          tabindex="0"
          class="disclosure-link"
          @keydown.enter.prevent="go(`/pages/journey/journey?id=${id}`)"
          @keydown.space.prevent
          @keyup.space.prevent="go(`/pages/journey/journey?id=${id}`)"
          @click="go(`/pages/journey/journey?id=${id}`)"
        >
          查看学习记录
          <uni-icons aria-hidden="true" type="right" size="18" />
        </button>
        <button
          aria-label="查看易错地图"
          role="button"
          tabindex="0"
          class="disclosure-link"
          @keydown.enter.prevent="go('/pages/error-map/error-map')"
          @keydown.space.prevent
          @keyup.space.prevent="go('/pages/error-map/error-map')"
          @click="go('/pages/error-map/error-map')"
        >
          查看易错地图
          <uni-icons aria-hidden="true" type="right" size="18" />
        </button>
      </template>
    </view>
  </view>
</template>
<script setup>
import MathText from '@/components/math-text/math-text.vue'
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
      : '开始订正'
    : step.key === 'practice'
      ? '练类似题'
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
    if (!id.value) throw new Error('请先打开一道错题，再查看学习安排。')
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
    if (version === revision) error.value = err.message || '学习安排暂时无法读取'
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
  margin: 16px 0 20px;
}
.repair-step {
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr);
  position: relative;
}
.repair-number {
  padding-top: 20px;
  font-size: 16px;
  font-weight: 500;
  color: var(--color-primary);
  font-variant-numeric: tabular-nums;
}
.repair-copy {
  padding: 16px 0 12px;
  border-top: 1px solid var(--color-border);
}
.repair-step:first-child .repair-copy {
  border-top: 0;
}
.repair-step.recommended .repair-copy {
  padding: 16px;
  border-radius: 12px;
  background: var(--color-primary-soft);
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
.repair-step-heading > .math-text {
  font-size: 16px;
  font-weight: 500;
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
.repair-step.recommended .route-action:not(.secondary-route) {
  padding: 8px 12px;
  border-radius: 8px;
  background: var(--color-primary);
  color: #fff;
}
.secondary-route {
  color: var(--color-text-secondary);
}
.repair-page .evidence-caption {
  display: block;
  margin: 24px 0;
}
</style>
