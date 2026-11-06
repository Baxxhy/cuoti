<template>
  <view class="page learning-page">
    <app-header title="到期复习" back back-fallback="/pages/learning/learning" />
    <view class="page-content">
      <button
        role="button"
        class="review-search-entry"
        @click="go('/pages/review-search/review-search')"
      >
        <uni-icons type="search" size="20" aria-hidden="true" />
        <text class="review-search-label">查找复习题</text>
        <uni-icons type="right" size="16" aria-hidden="true" />
      </button>
      <state-panel v-if="loading" state="loading" />
      <state-panel v-else-if="error" state="error" :message="error" @retry="load" />
      <template v-else>
        <text v-if="notice" class="review-notice" role="status">{{ notice }}</text>
        <view v-if="originUnavailable" class="origin-unavailable">
          <text class="origin-title">这条复习安排已不在待办中</text>
          <text class="previous-hint">可以回原题继续学习，其他待复习题仍可正常作答。</text>
          <button
            v-if="originText"
            class="previous-toggle"
            role="button"
            tabindex="0"
            :aria-expanded="showOriginText"
            @click="showOriginText = !showOriginText"
            @keydown.enter.prevent="showOriginText = !showOriginText"
            @keydown.space.prevent
            @keyup.space.prevent="showOriginText = !showOriginText"
          >
            {{ showOriginText ? '收起上次的文字' : '查看上次写下的文字' }}
          </button>
          <text v-if="originText && showOriginText" class="previous-text" selectable>
            {{ originText }}
          </text>
          <button
            class="missing-origin"
            :class="activePlan ? 'secondary-btn' : 'primary-btn'"
            role="button"
            tabindex="0"
            :disabled="queueBusy"
            :aria-disabled="queueBusy"
            @click="openMissingOriginal"
            @keydown.enter.prevent="openMissingOriginal"
            @keydown.space.prevent
            @keyup.space.prevent="openMissingOriginal"
          >
            返回原题
          </button>
        </view>
        <view v-if="!activePlan && !originUnavailable" class="today-summary">
          <b>{{ plans.length ? `${plans.length} 道复习等待完成` : '今天没有待复习题目' }}</b>
          <text>
            {{
              plans.length
                ? '先独立作答，再根据结果安排下一次复习。'
                : '复习会根据你的学习记录安排。'
            }}
          </text>
          <button
            role="button"
            v-if="!plans.length"
            class="primary-btn"
            @click="go('/pages/problem/list')"
          >
            查看错题
          </button>
        </view>

        <template v-if="activePlan">
          <view class="section-title">
            <text>今日复习</text>
            <text
              class="section-link"
              role="status"
              :aria-label="`当前第${activeIndex + 1}题，共${plans.length}题`"
            >
              {{ activeIndex + 1 }} / {{ plans.length }}
            </text>
          </view>
          <view id="active-review" class="review-card card">
            <view class="review-meta">
              <text class="tag">{{ activePlan.question?.subject }}</text>
              <text>{{ activePlan.question?.grade }}</text>
            </view>
            <math-text
              class="review-question"
              :text="activePlan.question?.question_text || '题目记录不可用'"
            />
            <image
              v-for="figure in activePlan.question?.question_figures || []"
              :key="figure.id || figure.url"
              class="review-figure"
              :src="figure.url"
              mode="widthFix"
            />
            <math-text class="review-reason" :text="friendlyReason(activePlan.reason)" inline />
            <template v-if="!attempts[activePlan.id]">
              <checkbox-group
                v-if="multiple && options.length"
                @change="setChoices($event.detail.value)"
              >
                <text class="review-reason">多选题，请选出所有符合条件的选项</text>
                <label v-for="option in options" :key="option.label" class="review-option">
                  <checkbox
                    :value="option.label"
                    :checked="selectedOptions.includes(option.label)"
                    :disabled="!!busy"
                    color="var(--color-primary)"
                  />
                  <math-text :text="`${option.label}. ${option.text}`" />
                </label>
              </checkbox-group>
              <radio-group
                v-else-if="options.length"
                @change="answers[activePlan.id] = $event.detail.value"
              >
                <label v-for="option in options" :key="option.label" class="review-option">
                  <radio
                    :value="option.label"
                    :checked="answers[activePlan.id] === option.label"
                    :disabled="!!busy"
                    color="var(--color-primary)"
                  />
                  <math-text :text="`${option.label}. ${option.text}`" />
                </label>
              </radio-group>
              <view v-else class="field">
                <text class="field-label">我的作答</text>
                <written-answer
                  :key="activePlan.id"
                  :disabled="!!busy"
                  ref="writtenAnswer"
                  v-model="answers[activePlan.id]"
                  placeholder="输入答案或关键步骤"
                  :allow-handwriting="allowsHandwriting"
                  upload-url="/answers/handwriting"
                  :upload-data="handwritingContext"
                  @handwriting-change="onHandwritingChange"
                  @uploading-change="uploadingHandwriting = $event"
                />
              </view>
              <button
                class="primary-btn"
                :aria-disabled="
                  busy === activePlan.id || uploadingHandwriting || !answers[activePlan.id]?.trim()
                "
                :disabled="
                  busy === activePlan.id || uploadingHandwriting || !answers[activePlan.id]?.trim()
                "
                role="button"
                tabindex="0"
                @keydown.enter.prevent="attempt(activePlan.id)"
                @keydown.space.prevent
                @keyup.space.prevent="attempt(activePlan.id)"
                @click="attempt(activePlan.id)"
              >
                {{
                  busy === activePlan.id
                    ? '正在判定…'
                    : uploadingHandwriting
                      ? '正在解析手写答案…'
                      : '提交作答'
                }}
              </button>
            </template>
            <template v-else>
              <view
                class="answer-result"
                :class="{
                  correct: attempts[activePlan.id].correct === true,
                  pending: !attempts[activePlan.id].can_update_learning,
                }"
              >
                <view class="result-title">
                  <uni-icons
                    aria-hidden="true"
                    :type="attemptIcon(attempts[activePlan.id])"
                    size="24"
                    :color="attemptColor(attempts[activePlan.id])"
                  />
                  <b>{{ attemptTitle(attempts[activePlan.id]) }}</b>
                </view>
                <math-text :text="learningFeedback(attempts[activePlan.id].feedback)" inline />
                <small>参考答案</small>
                <math-text :text="attempts[activePlan.id].expected_answer" />
                <text v-if="!attempts[activePlan.id].can_update_learning">
                  这次不会更新掌握度、错因或复习计划，可以修改答案后重新提交。
                </text>
              </view>
              <template v-if="attempts[activePlan.id].can_update_learning">
                <text class="grade-prompt">这道题掌握得怎么样？</text>
                <view class="grade-grid">
                  <button
                    v-for="gradeItem in grades"
                    :key="gradeItem.value"
                    :aria-disabled="busy === activePlan.id"
                    :disabled="busy === activePlan.id"
                    role="button"
                    tabindex="0"
                    @keydown.enter.prevent="grade(activePlan.id, gradeItem.value)"
                    @keydown.space.prevent
                    @keyup.space.prevent="grade(activePlan.id, gradeItem.value)"
                    @click="grade(activePlan.id, gradeItem.value)"
                  >
                    <text>{{ gradeItem.label }}</text>
                  </button>
                </view>
              </template>
              <button
                role="button"
                v-else
                class="secondary-btn"
                :disabled="!!busy"
                @click="clearAttempt(activePlan.id)"
              >
                修改后重新提交
              </button>
            </template>
            <view v-if="previousDraft && !attempts[activePlan.id]" class="previous-draft">
              <button
                class="previous-toggle"
                role="button"
                tabindex="0"
                :aria-expanded="showPrevious"
                @click="showPrevious = !showPrevious"
                @keydown.enter.prevent="showPrevious = !showPrevious"
                @keydown.space.prevent
                @keyup.space.prevent="showPrevious = !showPrevious"
              >
                {{ showPrevious ? '收起更新前的作答' : '查看更新前的作答' }}
              </button>
              <view v-if="showPrevious">
                <text class="previous-hint">题目或参考已更新，请核对后再使用旧文字。</text>
                <math-text class="previous-text" selectable :text="previousDraft.text" inline />
                <button
                  v-if="!answers[activePlan.id]?.trim()"
                  class="secondary-btn use-previous"
                  role="button"
                  tabindex="0"
                  :disabled="queueBusy"
                  :aria-disabled="queueBusy"
                  @click="usePreviousDraft"
                  @keydown.enter.prevent="usePreviousDraft"
                  @keydown.space.prevent
                  @keyup.space.prevent="usePreviousDraft"
                >
                  使用这份文字
                </button>
                <button
                  class="previous-dismiss"
                  role="button"
                  tabindex="0"
                  :disabled="queueBusy"
                  :aria-disabled="queueBusy"
                  @click="dismissPreviousDraft"
                  @keydown.enter.prevent="dismissPreviousDraft"
                  @keydown.space.prevent
                  @keyup.space.prevent="dismissPreviousDraft"
                >
                  不用这份文字
                </button>
              </view>
            </view>
            <button
              v-if="
                activePlan.question?.id &&
                (actionError || attempts[activePlan.id]?.can_update_learning === false)
              "
              class="secondary-btn review-origin"
              role="button"
              tabindex="0"
              :disabled="queueBusy"
              :aria-disabled="queueBusy"
              @click="openOriginal"
              @keydown.enter.prevent="openOriginal"
              @keydown.space.prevent
              @keyup.space.prevent="openOriginal"
            >
              回原题学习
            </button>
            <text v-if="cacheNotice" class="review-notice" role="status">{{ cacheNotice }}</text>
            <view v-if="actionError" class="review-error" role="alert">
              <text>{{ actionError }}</text>
              <text>当前内容已保留，可以重试；题目有更新时请重新读取。</text>
              <button role="button" class="secondary-btn" :disabled="!!busy" @click="load">
                重新读取复习
              </button>
            </view>
          </view>
          <view v-if="plans.length > 1" class="review-queue" aria-label="复习题目切换">
            <view class="queue-actions">
              <button
                class="queue-previous"
                role="button"
                tabindex="0"
                :disabled="queueBusy || activeIndex === 0"
                :aria-disabled="queueBusy || activeIndex === 0"
                @click="switchPlan(-1)"
                @keydown.enter.prevent="switchPlan(-1)"
                @keydown.space.prevent
                @keyup.space.prevent="switchPlan(-1)"
              >
                上一题
              </button>
              <button
                class="queue-next"
                role="button"
                tabindex="0"
                :disabled="queueBusy || activeIndex === plans.length - 1"
                :aria-disabled="queueBusy || activeIndex === plans.length - 1"
                @click="switchPlan(1)"
                @keydown.enter.prevent="switchPlan(1)"
                @keydown.space.prevent
                @keyup.space.prevent="switchPlan(1)"
              >
                下一题
              </button>
            </view>
            <text class="queue-hint">切换不记为完成，作答会保留。</text>
          </view>
        </template>

        <button
          class="history-toggle"
          role="button"
          tabindex="0"
          :aria-expanded="showReinforce"
          @click="toggleReinforce"
          @keydown.enter.prevent="toggleReinforce"
        >
          <text>巩固建议</text>
          <uni-icons
            :type="showReinforce ? 'top' : 'bottom'"
            size="24"
            color="var(--color-text-secondary)"
            aria-hidden="true"
          />
        </button>
        <view v-if="showReinforce" class="reinforce-list">
          <view
            v-for="item in reportCauses(dashboard.misconceptions || []).slice(0, 4)"
            :key="item.label"
          >
            <math-text :text="item.label" class="reinforce-reason" />

            <button role="button" class="row-action" @click="go('/pages/problem/list')">
              查看错题
            </button>
          </view>
          <text v-if="!reportCauses(dashboard.misconceptions || []).length" class="muted">
            暂无需要巩固的错因
          </text>
        </view>

        <button
          class="history-toggle"
          role="button"
          tabindex="0"
          :aria-expanded="showHistory"
          @click="toggleHistory"
          @keydown.enter.prevent="toggleHistory"
        >
          <text>复习历史</text>
          <uni-icons
            :type="showHistory ? 'top' : 'bottom'"
            size="24"
            color="var(--color-text-secondary)"
            aria-hidden="true"
          />
        </button>
        <view v-if="showHistory">
          <text v-if="!history.length && !secondaryError" class="muted">暂无已完成的复习记录</text>
          <view v-for="item in history.slice(0, 8)" :key="item.id" class="list-card">
            <view class="history-score" :class="{ correct: item.correct }">
              <uni-icons
                aria-hidden="true"
                :type="item.correct ? 'checkmarkempty' : 'reload'"
                size="22"
                color="var(--color-text-secondary)"
              />
            </view>
            <view class="list-main">
              <math-text
                class="list-title"
                :text="item.question?.question_text || '复习题目'"
                inline
              />
              <button
                role="button"
                v-if="item.question?.id && item.question.status !== 'archived'"
                class="history-link"
                @click="go(`/pages/detail/detail?id=${item.question.id}`)"
              >
                查看原题与学习记录
              </button>
              <text class="list-desc">
                {{ item.correct ? '作答正确' : '仍需巩固' }} ·
                {{ gradeLabel[item.grade] || '已完成' }}
              </text>
            </view>
          </view>
        </view>
        <view v-if="secondaryError" class="review-error" role="alert">
          <text>{{ secondaryError }}</text>
          <button role="button" class="secondary-btn" @click="loadSecondary()">重新读取记录</button>
        </view>
      </template>
    </view>
  </view>
</template>

<script setup>
import { reportCauses } from '@/utils/report.js'
import { learningFeedback } from '@/utils/learning-feedback.js'
import MathText from '@/components/math-text/math-text.vue'
import WrittenAnswer from '@/components/written-answer/written-answer.vue'

import { computed, nextTick, reactive, ref, watch } from 'vue'
import { onLoad, onShow, onHide, onUnload } from '@dcloudio/uni-app'
import { getData, postData } from '@/api/index.js'
import { go } from '@/utils/navigation.js'
import { choiceAnswer, isMultipleChoice, normalizeOptions } from '@/utils/question.js'
import {
  readReviewDraft,
  reconcileReviewDraft,
  readReviewText,
  saveReviewDraft,
  reviewSubmission,
  readReviewPosition,
  saveReviewPosition,
} from '@/utils/review-draft.js'
const error = ref(''),
  actionError = ref(''),
  cacheNotice = ref(''),
  notice = ref('')
const previousDraft = ref(null),
  showPrevious = ref(false)
const originPlanId = ref(''),
  originQuestionId = ref(''),
  originUnavailable = ref(false),
  originText = ref(''),
  showOriginText = ref(false)
let originOwnerId = ''
const drafts = new Map()
const switching = ref(false)
const userId = ref(''),
  showReinforce = ref(false),
  secondaryError = ref('')
let active = false,
  revision = 0,
  accountToken = '',
  pending = null,
  dismissedAttempt = '',
  operation = 0,
  restoring = false
const plans = ref([]),
  history = ref([]),
  dashboard = ref({}),
  loading = ref(true),
  busy = ref(''),
  answers = reactive({}),
  attempts = reactive({}),
  activeId = ref(''),
  showHistory = ref(false),
  writtenAnswer = ref(null),
  uploadingHandwriting = ref(false),
  handwritingImage = ref(''),
  handwritingRecognition = ref(null)
const grades = [
    { value: 'again', label: '还不会' },
    { value: 'hard', label: '有点困难' },
    { value: 'good', label: '基本掌握' },
    { value: 'easy', label: '很轻松' },
  ],
  gradeLabel = { again: '还不会', hard: '有点困难', good: '基本掌握', easy: '很轻松' }
const activeIndex = computed(() =>
    Math.max(
      0,
      plans.value.findIndex((item) => item.id === activeId.value),
    ),
  ),
  activePlan = computed(() => plans.value[activeIndex.value] || null)
const queueBusy = computed(
  () => !!busy.value || uploadingHandwriting.value || switching.value || loading.value,
)
const options = computed(() => normalizeOptions(activePlan.value?.question?.options))
const multiple = computed(() => isMultipleChoice(activePlan.value?.question?.question_type))
const selectedOptions = computed(() => String(answers[activePlan.value?.id] || '').split('、'))
function setChoices(values) {
  answers[activePlan.value.id] = choiceAnswer(values, activePlan.value.question.options)
}
const allowsHandwriting = computed(() => !activePlan.value?.question?.options?.length),
  handwritingContext = computed(() => ({
    context_type: 'review',
    context_id: activePlan.value?.id || '',
  }))
function current(stamp) {
  return (
    active &&
    stamp === revision &&
    uni.getStorageSync('minddimension_access_token') === accountToken
  )
}
function saveDraft() {
  if (restoring || !active || !userId.value || !activePlan.value) return
  drafts.set(`${userId.value}:${activePlan.value.id}`, {
    fingerprint: activePlan.value.source_version || '',
    text: answers[activePlan.value.id] || '',
    pending,
    image: handwritingImage.value,
    recognition: handwritingRecognition.value,
    dismissed_attempt: dismissedAttempt,
    previous_draft: previousDraft.value,
  })
  const saved = saveReviewDraft(
    userId.value,
    activePlan.value,
    answers[activePlan.value.id],
    pending,
    handwritingImage.value,
    handwritingRecognition.value,
    dismissedAttempt,
    previousDraft.value,
  )
  const positionSaved = saveReviewPosition(userId.value, activePlan.value.id)
  cacheNotice.value = saved && positionSaved ? '' : '本机暂时无法保存草稿，请保持此页打开后提交。'
}
watch(answers, saveDraft, { deep: true, flush: 'sync' })
async function load() {
  if (!active) return
  const stamp = ++revision
  accountToken = uni.getStorageSync('minddimension_access_token')
  loading.value = true
  uploadingHandwriting.value = false
  error.value = ''
  actionError.value = ''
  cacheNotice.value = ''
  try {
    const [user, nextPlans] = await Promise.all([
      getData('/auth/me', { silent: true }),
      getData('/reviews/today'),
    ])
    if (!current(stamp)) return
    restoring = true
    userId.value = user.id
    if (originOwnerId && originOwnerId !== user.id) {
      originPlanId.value = ''
      originQuestionId.value = ''
    }
    originOwnerId = user.id
    originUnavailable.value =
      !!originPlanId.value &&
      !!originQuestionId.value &&
      !nextPlans.some((plan) => plan.id === originPlanId.value)
    originText.value = originUnavailable.value
      ? readReviewText(user.id, originPlanId.value, drafts.get(`${user.id}:${originPlanId.value}`))
      : ''
    showOriginText.value = false
    for (const key of Object.keys(answers)) delete answers[key]
    for (const key of Object.keys(attempts)) delete attempts[key]
    plans.value = nextPlans
    if (!nextPlans.some((item) => item.id === activeId.value)) {
      const remembered = readReviewPosition(user.id)
      activeId.value =
        nextPlans.find((item) => item.id === remembered)?.id || nextPlans[0]?.id || ''
    }
    restoring = false
    loading.value = false
    await restorePlan(stamp)
    if (!current(stamp)) return
    if (showHistory.value || showReinforce.value) await loadSecondary(stamp)
  } catch (err) {
    if (current(stamp)) error.value = err.message || '复习暂时无法加载，请重试。'
  } finally {
    restoring = false
    if (current(stamp)) loading.value = false
  }
}
async function restorePlan(stamp) {
  restoring = true
  pending = null
  dismissedAttempt = ''
  previousDraft.value = null
  showPrevious.value = false
  handwritingImage.value = ''
  handwritingRecognition.value = null
  if (activePlan.value) {
    const plan = activePlan.value,
      cached = drafts.get(`${userId.value}:${plan.id}`)
    const draft = cached ? reconcileReviewDraft(cached, plan) : readReviewDraft(userId.value, plan)
    previousDraft.value = draft.previous_draft || null
    showPrevious.value = false
    pending = draft.pending || null
    dismissedAttempt = draft.dismissed_attempt || ''
    const latest = attempts[plan.id] || plan.pending_attempt
    const receipt = latest?.attempt_id !== dismissedAttempt ? latest : null
    answers[plan.id] = receipt?.student_answer ?? draft.text ?? ''
    if (receipt) {
      attempts[plan.id] = receipt
      pending = null
    } else {
      delete attempts[plan.id]
      handwritingImage.value = draft.image || ''
      handwritingRecognition.value = draft.recognition || null
    }
  }
  restoring = false
  await nextTick()
  if (!current(stamp)) return
  if (handwritingImage.value)
    writtenAnswer.value?.restore({
      image_url: handwritingImage.value,
      recognition: handwritingRecognition.value,
    })
  saveDraft()
}
async function switchPlan(delta) {
  if (queueBusy.value || !current(revision)) return
  const target = plans.value[activeIndex.value + delta]
  if (!target) return
  saveDraft()
  switching.value = true
  const stamp = ++revision
  activeId.value = target.id
  notice.value = ''
  actionError.value = ''
  try {
    await restorePlan(stamp)
  } finally {
    if (current(stamp)) switching.value = false
  }
}

function openOriginal() {
  if (queueBusy.value || !current(revision) || !activePlan.value?.question?.id) return
  saveDraft()
  originPlanId.value = activePlan.value.id
  originQuestionId.value = activePlan.value.question.id
  originOwnerId = userId.value
  go(
    `/pages/detail/detail?id=${encodeURIComponent(activePlan.value.question.id)}&review=${encodeURIComponent(activePlan.value.id)}`,
  )
}
function openMissingOriginal() {
  if (queueBusy.value || !current(revision) || !originQuestionId.value) return
  saveDraft()
  go(
    `/pages/detail/detail?id=${encodeURIComponent(originQuestionId.value)}&review=${encodeURIComponent(originPlanId.value)}`,
  )
}

function usePreviousDraft() {
  if (
    queueBusy.value ||
    !current(revision) ||
    !previousDraft.value ||
    answers[activePlan.value?.id]?.trim()
  )
    return
  const text = previousDraft.value.text
  previousDraft.value = null
  pending = null
  dismissedAttempt = ''
  answers[activePlan.value.id] = text
  saveDraft()
}
function dismissPreviousDraft() {
  if (queueBusy.value || !current(revision)) return
  previousDraft.value = null
  showPrevious.value = false
  saveDraft()
}

async function loadSecondary(stamp = revision) {
  secondaryError.value = ''
  try {
    const [nextHistory, nextDashboard] = await Promise.all([
      showHistory.value
        ? getData('/reviews/history', { silent: true })
        : Promise.resolve(history.value),
      showReinforce.value
        ? getData('/dashboard', { silent: true })
        : Promise.resolve(dashboard.value),
    ])
    if (!current(stamp)) return
    history.value = nextHistory
    dashboard.value = nextDashboard
  } catch {
    if (current(stamp)) secondaryError.value = '补充记录暂时无法读取，请重试。'
  }
}
function toggleHistory() {
  showHistory.value = !showHistory.value
  if (showHistory.value) loadSecondary()
}
function toggleReinforce() {
  showReinforce.value = !showReinforce.value
  if (showReinforce.value) loadSecondary()
}

function friendlyReason(value) {
  if (!value) return '上次这道题掌握还不稳定，今天再试一次。'
  return value
    .replace(/演示错因需次日复习/g, '上次这道题掌握还不稳定，今天再试一次。')
    .replace(/again/gi, '还需要再练习')
}
function onHandwritingChange(value) {
  handwritingImage.value = value.image_url || ''
  handwritingRecognition.value = value.recognition || null
  saveDraft()
}
function resetHandwriting() {
  writtenAnswer.value?.reset()
  handwritingImage.value = ''
  handwritingRecognition.value = null
  uploadingHandwriting.value = false
}
function attemptTitle(item) {
  if (!item.can_update_learning)
    return item.grading?.verdict === 'probably_correct'
      ? '可能正确，暂不计入记录'
      : '需要核对，暂不判对错'
  return item.correct ? '回答正确' : '这次还没有答对'
}
function attemptIcon(item) {
  return !item.can_update_learning ? 'info-filled' : item.correct ? 'checkbox-filled' : 'clear'
}
function attemptColor(item) {
  return !item.can_update_learning ? '#718096' : item.correct ? '#168A45' : '#E94B4B'
}
function clearAttempt(id) {
  dismissedAttempt = attempts[id]?.attempt_id || ''
  delete attempts[id]
  pending = null
  actionError.value = ''
  saveDraft()
}
async function attempt(id) {
  if (
    busy.value ||
    uploadingHandwriting.value ||
    !answers[id]?.trim() ||
    !active ||
    activePlan.value?.id !== id
  )
    return
  const stamp = revision,
    plan = activePlan.value
  busy.value = id
  actionError.value = ''
  notice.value = ''
  pending = reviewSubmission(
    plan,
    answers[id],
    handwritingImage.value,
    handwritingRecognition.value,
    pending,
  )
  const submission = pending
  saveDraft()
  try {
    const receipt = await postData(`/reviews/${id}/attempt`, {
      ...submission.payload,
      request_id: submission.request_id,
    })
    if (!current(stamp)) return
    attempts[id] = receipt
    previousDraft.value = null
    pending = null
    saveDraft()
  } catch (err) {
    if (current(stamp)) {
      actionError.value = err.message || '答案未能确认，请重试。'
      // A lost response may already have a persisted result. Only the server
      // decides whether it is valid for this question version.
      try {
        const next = await getData('/reviews/today', { silent: true })
        if (current(stamp)) {
          const fresh = next.find((item) => item.id === id)
          if (
            fresh?.source_version === plan.source_version &&
            fresh?.pending_attempt?.request_id === submission.request_id
          ) {
            attempts[id] = fresh.pending_attempt
            answers[id] = fresh.pending_attempt.student_answer
            pending = null
            actionError.value = ''
            notice.value = '已找回刚才的判题结果。'
            saveDraft()
          }
        }
      } catch {
        /* Keep the pending payload and visible retry feedback. */
      }
    }
  } finally {
    if (current(stamp)) busy.value = ''
  }
}
async function finishGrade(id) {
  if (originPlanId.value === id) {
    originPlanId.value = ''
    originQuestionId.value = ''
    originUnavailable.value = false
  }
  const nextId = plans.value[activeIndex.value + 1]?.id || ''
  drafts.delete(`${userId.value}:${id}`)
  restoring = true
  delete attempts[id]
  delete answers[id]
  pending = null
  saveReviewDraft(userId.value, activePlan.value, '')
  resetHandwriting()
  restoring = false
  notice.value = '本次复习已记录。'
  activeId.value = nextId
  await load()
}
async function grade(id, value) {
  if (busy.value || !active || !attempts[id]?.can_update_learning) return
  busy.value = id
  actionError.value = ''
  const action = ++operation
  const stamp = revision,
    receiptId = attempts[id].attempt_id
  try {
    await postData(`/reviews/${id}/grade`, { grade: value, attempt_id: receiptId })
    if (current(stamp)) await finishGrade(id)
  } catch (err) {
    if (!current(stamp)) return
    actionError.value = err.message || '复习评价未能确认，请重试。'
    try {
      const records = await getData('/reviews/history', { silent: true })
      if (
        current(stamp) &&
        records.some(
          (record) =>
            record.id === receiptId &&
            record.plan?.id === id &&
            record.plan?.status === 'completed',
        )
      ) {
        actionError.value = ''
        await finishGrade(id)
      }
    } catch {
      /* A repeated grade is never assumed successful without history. */
    }
  } finally {
    if (action === operation) busy.value = ''
  }
}
onLoad((query) => {
  activeId.value = query.plan || ''
  if (typeof query.question === 'string' && query.question.length <= 80) {
    originPlanId.value = activeId.value
    originQuestionId.value = query.question
  }
  showHistory.value = query.history === '1'
})
onShow(() => {
  active = true
  load()
})
function leave() {
  saveDraft()
  active = false
  switching.value = false
  operation++
  revision++
  userId.value = ''
  plans.value = []
  history.value = []
  dashboard.value = {}
  busy.value = ''
  actionError.value = ''
  notice.value = ''
  loading.value = true
  uploadingHandwriting.value = false
}
onHide(leave)
onUnload(leave)
</script>

<style scoped lang="scss">
.review-search-entry {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  min-height: 48px;
  margin: 0 0 16px;
  padding: 10px 14px;
  background: var(--color-surface);
  border-radius: 10px;
  font-size: 15px;
  text-align: left;
}
.review-search-label {
  flex: 1;
  min-width: 0;
}
.review-search-entry :deep(.uni-icons) {
  flex: none;
}
.origin-unavailable {
  padding: 16px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  margin-bottom: 20px;
}
.origin-title {
  display: block;
  font-size: 16px;
  font-weight: 600;
  line-height: 1.6;
}

.previous-draft {
  border-top: 1px solid var(--color-border);
  margin-top: 16px;
  padding-top: 12px;
}
.previous-toggle,
.previous-dismiss {
  background: transparent;
  color: var(--color-primary);
  min-height: 44px;
  padding: 8px 0;
  text-align: left;
  font-size: 14px;
}
.previous-hint {
  display: block;
  font-size: 14px;
  color: var(--color-text-secondary);
  line-height: 1.6;
  margin: 8px 0;
}
.previous-text {
  display: block;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-size: 16px;
  line-height: 1.6;
  padding: 12px;
  background: var(--color-surface-subtle);
  border-radius: 8px;
}
.review-origin {
  margin-top: 16px;
}

.section-title {
  gap: 12px;
  align-items: flex-start;
}
.section-title > text:first-child {
  min-width: 0;
}
.section-link {
  flex-shrink: 0;
  white-space: nowrap;
}
.review-queue {
  margin-top: 16px;
}
.queue-actions {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 12px;
}
.queue-actions button {
  margin: 0;
  min-height: 48px;
  padding: 12px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 10px;
  color: var(--color-primary);
  font-size: 16px;
}
.queue-actions button[disabled] {
  color: var(--color-text-secondary);
  opacity: 0.55;
}
.queue-hint {
  display: block;
  font-size: 14px;
  color: var(--color-text-secondary);
  line-height: 1.6;
  margin-top: 8px;
}

.review-notice {
  display: block;
  color: var(--color-text-secondary);
  line-height: 1.6;
  margin-bottom: 16px;
}
.review-error {
  padding: 16px;
  margin-top: 16px;
  background: var(--color-error-soft);
  color: var(--color-error);
  border-radius: 12px;
  line-height: 1.6;
}
.review-error > text {
  display: block;
}
.review-error > text + text {
  margin-top: 8px;
  font-size: 14px;
}
.review-card {
  padding: 20px;
}
.review-card .field-label {
  font-size: 16px;
}

.review-figure {
  display: block;
  width: 100%;
  margin-top: 18rpx;
}
.review-option {
  display: flex;
  align-items: flex-start;
  gap: 14rpx;
  padding: 20rpx 0;
  border-bottom: 1rpx solid var(--color-border);
}
.review-option :deep(.math-text) {
  flex: 1;
  min-width: 0;
}

.continue-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24rpx 0;
  border-bottom: 1rpx solid var(--color-border);
}
.continue-row text,
.continue-row b,
.continue-row small {
  display: block;
}
.continue-row > view > text {
  font-size: 22rpx;
  color: var(--color-primary);
}
.continue-row b {
  font-size: 30rpx;
  margin-top: 3rpx;
}
.continue-row small {
  font-size: 23rpx;
  color: var(--color-text-secondary);
  margin-top: 3rpx;
}
.row-action {
  background: transparent;
  min-height: 44px;
  margin: 0;
  padding: 8px;
  color: var(--color-primary);
  font-size: 24rpx;
}
.today-summary {
  padding: 4px 0 24px;
}
.today-summary > text,
.today-summary > b {
  display: block;
}
.summary-label {
  font-size: 23rpx;
  color: var(--color-primary);
  font-weight: 600;
}
.today-summary b {
  font-size: 34rpx;
  margin-top: 6rpx;
}
.today-summary > b + text {
  font-size: 24rpx;
  color: var(--color-text-secondary);
  margin-top: 8rpx;
}
.review-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: var(--color-text-secondary);
  font-size: 22rpx;
}
.review-question {
  display: block;
  font-size: 30rpx;
  font-weight: 500;
  line-height: 1.7;
  margin-top: 20rpx;
}
.review-reason {
  display: block;
  color: var(--color-text-secondary);
  font-size: 23rpx;
  margin-top: 10rpx;
}
.answer-result {
  margin-top: 24rpx;
  padding: 24rpx;
  border-radius: 20rpx;
  background: var(--color-error-soft);
  color: #8f3030;
}
.answer-result.correct {
  background: var(--color-primary-soft);
  color: var(--color-primary-dark);
}
.answer-result.pending {
  background: #f4f6f8;
  color: #526174;
}
.result-title {
  display: flex;
  align-items: center;
  gap: 10rpx;
}
.answer-result > text,
.answer-result small,
.answer-result strong {
  display: block;
  margin-top: 10rpx;
}
.answer-result strong {
  white-space: pre-wrap;
}
.grade-prompt {
  display: block;
  font-weight: 600;
  margin: 24rpx 0 12rpx;
}
.grade-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  max-width: 640px;
}
.grade-grid button {
  display: flex;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  width: 100%;
  min-width: 0;
  height: 44px;
  min-height: 44px;
  margin: 0;
  padding: 0 12px;
  border: 1px solid var(--color-border);
  background: var(--color-surface);
  color: var(--color-text-primary);
  border-radius: 8px;
  font-size: 14px;
  font-weight: 400;
  line-height: 1.4;
}
.grade-grid button::after {
  border: 0;
}
.grade-grid button:not([disabled]):active {
  background: var(--color-primary-soft);
  border-color: var(--color-primary);
  color: var(--color-primary);
}
.grade-grid button:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}
.grade-grid button[disabled] {
  opacity: 0.5;
}
@media (min-width: 600px) {
  .grade-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}
.reinforce-list {
  border-top: 1rpx solid var(--color-border);
}
.reinforce-list > view {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 4rpx;
  padding: 20rpx 2rpx;
  border-bottom: 1rpx solid var(--color-border);
}
.reinforce-reason {
  min-width: 0;
  font-size: 14px;
  line-height: 1.7;
}
.reinforce-list small {
  grid-row: 2;
  color: var(--color-text-secondary);
  font-size: 22rpx;
}
.reinforce-list .row-action {
  background: transparent;
  min-height: 44px;
  margin: 0;
  padding: 8px;
  grid-row: 1/3;
  grid-column: 2;
  align-self: center;
}
.history-toggle {
  width: 100%;
  text-align: left;
  background: transparent;
  border-radius: 0;
  min-height: 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 38rpx;
  padding: 24rpx 0;
  border-top: 1rpx solid var(--color-border);
  font-size: 29rpx;
}
.history-score {
  width: 64rpx;
  height: 64rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 18rpx;
  background: var(--color-error-soft);
  color: var(--color-error);
  font-weight: 600;
}
.history-score.correct {
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.history-link {
  background: transparent;
  color: var(--color-primary);
  font-size: 13px;
  min-height: 44px;
  text-align: left;
  padding: 10px 0;
}
</style>
