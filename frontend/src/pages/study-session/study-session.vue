<template>
  <view class="page study-page">
    <app-header :title="session?.title || '练习与考试'" back back-fallback="/pages/bank/bank">
      <text
        v-if="session?.mode === 'exam' && session?.status === 'active'"
        class="exam-clock"
        :class="{ urgent: remaining < 60 }"
        role="timer"
        aria-label="剩余时间"
      >
        {{ clock }}
      </text>
    </app-header>
    <view class="page-content">
      <state-panel
        v-if="loading || loadError"
        :state="loadError ? 'error' : 'loading'"
        :message="loadError"
        @retry="load"
      />
      <template v-else-if="session">
        <template v-if="session.status === 'submitted'">
          <view class="result-summary" :class="{ exam: session.mode === 'exam' }">
            <text class="result-title">{{ session.mode === 'exam' ? '已交卷' : '练习完成' }}</text>
            <view class="result-score">
              <text>{{ session.results.score }}</text>
              <small>/ {{ session.results.max_score }} 分</small>
            </view>
            <text class="result-meta">
              答对 {{ session.results.correct }} / {{ session.results.total }} 题
              <template v-if="session.results.pending">
                · {{ session.results.pending }} 题待核对
              </template>
            </text>
            <text v-if="session.results.pending" class="pending-note">当前显示已确认得分。</text>
          </view>
          <view v-for="(item, index) in session.items" :key="item.id" class="answer-review card">
            <view class="review-heading">
              <text>第 {{ index + 1 }} 题</text>
              <text class="verdict" :class="verdictClass(item)">{{ verdict(item) }}</text>
            </view>
            <math-text :text="item.question.question_text" />
            <view
              v-for="option in normalizeOptions(item.question.options)"
              :key="option.label"
              class="review-option"
            >
              <text>{{ option.label }}.</text>
              <math-text :text="option.text" />
            </view>
            <image
              v-for="url in item.question.image_urls || []"
              :key="url"
              :src="mediaUrl(url)"
              mode="widthFix"
              class="question-image"
            />
            <view class="review-answers">
              <view>
                <text class="answer-label">我的答案</text>
                <math-text :text="answerText(item.student_answer)" />
              </view>
              <view>
                <text class="answer-label">参考答案</text>
                <math-text :text="answerText(item.answer)" />
              </view>
            </view>
            <math-text v-if="item.solution" class="reference-solution" :text="item.solution" />
            <text v-if="item.grading?.feedback" class="grading-feedback">
              {{ item.grading.feedback }}
            </text>
            <button
              role="button"
              v-if="
                item.grading?.can_update_learning &&
                item.grading?.correct === false &&
                !item.question.image_urls?.length
              "
              class="small-btn add-mistake"
              :disabled="adding === item.id || added.has(item.id)"
              @click="addMistake(item)"
            >
              {{ added.has(item.id) ? '已加入错题本' : '加入错题本' }}
            </button>
          </view>
          <button role="button" class="secondary-btn" @click="backToBank">
            返回{{ session.mode === 'exam' ? '模拟考试' : '题库' }}
          </button>
        </template>
        <template v-else-if="current">
          <view class="session-toolbar">
            <text>第 {{ currentIndex + 1 }} / {{ session.items.length }} 题</text>
            <text class="save-status" role="status">
              {{ saving ? '正在保存…' : saved ? '作答已保存' : '有未保存作答' }}
            </text>
          </view>
          <view class="answer-progress">
            <view :style="{ width: `${(answered / session.items.length) * 100}%` }" />
          </view>
          <view class="question-workspace card">
            <view class="question-category">
              <text>{{ current.question.subject }}</text>
              <text>{{ questionTypeLabel(current.question.question_type) }}</text>
              <text>5 分</text>
            </view>
            <math-text class="question-stem" :text="current.question.question_text" />
            <image
              v-for="url in current.question.image_urls || []"
              :key="url"
              :src="mediaUrl(url)"
              mode="widthFix"
              class="question-image"
            />
            <view v-if="options.length" class="answer-options">
              <button
                role="button"
                v-for="option in options"
                :key="option.label"
                :aria-pressed="selected(option.label)"
                :class="{ selected: selected(option.label) }"
                :disabled="submitting || expired"
                @click="select(option.label)"
              >
                <text class="option-letter">{{ option.label }}</text>
                <math-text :text="option.text" />
                <uni-icons
                  v-if="selected(option.label)"
                  type="checkmarkempty"
                  size="20"
                  color="var(--color-primary)"
                />
              </button>
            </view>
            <view v-else class="field">
              <text class="field-label">我的作答</text>
              <textarea
                class="field-textarea study-answer"
                :value="answers[current.id] || ''"
                :disabled="submitting || expired"
                maxlength="3000"
                placeholder="写下你的答案"
                @input="setAnswer($event.detail.value)"
              />
            </view>
          </view>
          <view class="question-navigation">
            <button
              role="button"
              class="secondary-btn"
              :disabled="currentIndex === 0 || submitting"
              @click="currentIndex--"
            >
              <uni-icons type="left" size="16" />
              上一题
            </button>
            <button
              role="button"
              class="secondary-btn"
              :disabled="currentIndex === session.items.length - 1 || submitting"
              @click="currentIndex++"
            >
              下一题
              <uni-icons type="right" size="16" />
            </button>
          </view>
          <view class="question-grid" aria-label="答题卡">
            <button
              role="button"
              v-for="(item, index) in session.items"
              :key="item.id"
              :class="{ current: index === currentIndex, answered: hasAnswer(answers[item.id]) }"
              :aria-label="`第${index + 1}题`"
              @click="currentIndex = index"
            >
              {{ index + 1 }}
            </button>
          </view>
          <view class="submit-row">
            <text>已答 {{ answered }} / {{ session.items.length }} 题</text>
            <button role="button" class="primary-btn" :disabled="submitting" @click="confirmSubmit">
              {{ submitting ? '正在交卷判分…' : '交卷并查看结果' }}
            </button>
          </view>
        </template>
        <view v-if="actionError" class="account-notice" role="alert">
          <text>{{ actionError }}</text>
          <view v-if="session.status === 'active'" class="question-navigation">
            <button
              role="button"
              v-if="!expired && !saved"
              class="secondary-btn"
              :disabled="saving || submitting"
              @click="flush().catch(() => {})"
            >
              重试保存
            </button>
            <button
              role="button"
              class="secondary-btn"
              :disabled="saving || submitting"
              @click="load"
            >
              读取已保存作答
            </button>
          </view>
        </view>
      </template>
    </view>
  </view>
</template>
<script setup>
import { computed, ref } from 'vue'
import { onLoad, onHide, onUnload } from '@dcloudio/uni-app'
import { getData, patchData, postData, mediaUrl } from '@/api/index.js'
import { go } from '@/utils/navigation.js'
import { normalizeOptions, isMultipleChoice, questionTypeLabel } from '@/utils/question.js'
const id = ref(''),
  session = ref(null),
  loading = ref(true),
  loadError = ref(''),
  actionError = ref(''),
  currentIndex = ref(0),
  answers = ref({}),
  saving = ref(false),
  saved = ref(true),
  submitting = ref(false),
  remaining = ref(0),
  added = ref(new Set()),
  adding = ref('')
let saveTimer,
  tick,
  serverTime = 0,
  receivedAt = 0,
  revision = 0,
  savedRevision = 0,
  savePromise = null,
  disposed = false,
  autoSubmitted = false
const current = computed(() => session.value?.items?.[currentIndex.value])
const options = computed(() => normalizeOptions(current.value?.question?.options))
const expired = computed(() => session.value?.mode === 'exam' && remaining.value <= 0)
const clock = computed(
  () =>
    `${String(Math.floor(remaining.value / 60)).padStart(2, '0')}:${String(remaining.value % 60).padStart(2, '0')}`,
)
function hasAnswer(value) {
  return Array.isArray(value) ? value.length > 0 : !!String(value || '').trim()
}
const answered = computed(
  () => (session.value?.items || []).filter((item) => hasAnswer(answers.value[item.id])).length,
)
function syncTime(data) {
  serverTime = data.remaining_seconds || 0
  receivedAt = Date.now()
  remaining.value = serverTime
}
function draftKey() {
  return `study-draft:${session.value.user_id}:${id.value}`
}
function keepDraft() {
  try {
    uni.setStorageSync(
      draftKey(),
      JSON.parse(JSON.stringify({ version: session.value.version, answers: answers.value })),
    )
  } catch (_) {}
}
function removeDraft() {
  try {
    uni.removeStorageSync(draftKey())
  } catch (_) {}
}
async function load() {
  loading.value = true
  loadError.value = ''
  actionError.value = ''
  clearTimeout(saveTimer)
  clearInterval(tick)
  try {
    const data = await getData(`/study-sessions/${encodeURIComponent(id.value)}`, { silent: true })
    if (disposed) return
    session.value = data
    answers.value = Object.fromEntries(data.items.map((item) => [item.id, item.student_answer]))
    saved.value = true
    savedRevision = revision
    syncTime(data)
    autoSubmitted = false
    let draft
    try {
      draft = uni.getStorageSync(draftKey())
    } catch (_) {}
    if (
      data.status === 'active' &&
      !expired.value &&
      draft?.version === data.version &&
      draft.answers
    ) {
      for (const item of data.items) {
        if (Object.prototype.hasOwnProperty.call(draft.answers, item.id))
          answers.value[item.id] = draft.answers[item.id]
      }
      revision++
      saved.value = false
      saveTimer = setTimeout(() => flush().catch(() => {}), 0)
    } else if (draft) {
      removeDraft()
      if (data.status === 'active' && !expired.value)
        actionError.value = '作答已在其他页面更新，已读取最新保存内容。'
    }
    clearInterval(tick)
    if (data.mode === 'exam' && data.status === 'active') {
      tick = setInterval(() => {
        remaining.value = Math.max(0, serverTime - Math.floor((Date.now() - receivedAt) / 1000))
        if (remaining.value === 0 && !submitting.value && !autoSubmitted) {
          autoSubmitted = true
          submit()
        }
      }, 1000)
      if (data.expired) {
        autoSubmitted = true
        submit()
      }
    }
  } catch (e) {
    loadError.value = e.message || '暂时无法读取练习'
  } finally {
    loading.value = false
  }
}
function selected(label) {
  return (
    Array.isArray(answers.value[current.value?.id]) &&
    answers.value[current.value.id].includes(label)
  )
}
function select(label) {
  const old = answers.value[current.value.id] || []
  setAnswer(
    isMultipleChoice(current.value.question.question_type)
      ? old.includes(label)
        ? old.filter((x) => x !== label)
        : [...old, label]
      : [label],
  )
}
function setAnswer(value) {
  if (submitting.value || expired.value) return
  answers.value[current.value.id] = value
  revision++
  saved.value = false
  keepDraft()
  clearTimeout(saveTimer)
  saveTimer = setTimeout(() => flush().catch(() => {}), 600)
}
async function flush() {
  clearTimeout(saveTimer)
  if (savePromise) {
    await savePromise
    if (savedRevision !== revision) return flush()
    return
  }
  if (
    savedRevision === revision ||
    !session.value ||
    session.value.status !== 'active' ||
    expired.value
  )
    return
  const sentRevision = revision
  const body = {
    version: session.value.version,
    answers: session.value.items.map((item) => ({
      id: item.id,
      answer: answers.value[item.id] ?? null,
    })),
  }
  saving.value = true
  actionError.value = ''
  savePromise = patchData(`/study-sessions/${id.value}`, body, { silent: true })
    .then((data) => {
      session.value.version = data.version
      syncTime(data)
      savedRevision = sentRevision
      saved.value = sentRevision === revision
      if (saved.value) removeDraft()
      else keepDraft()
    })
    .catch(async (e) => {
      if (e.statusCode === 409) {
        const latest = await getData(`/study-sessions/${id.value}`, { silent: true }).catch(
          () => null,
        )
        if (latest && latest.version === session.value.version) syncTime(latest)
      }
      actionError.value = e.message || '作答暂未保存，请重试'
      throw e
    })
    .finally(() => {
      saving.value = false
      savePromise = null
    })
  await savePromise
  if (savedRevision !== revision) return flush()
}
function confirmSubmit() {
  if (submitting.value) return
  uni.showModal({
    title: '确认交卷',
    content:
      answered.value < session.value.items.length
        ? `还有 ${session.value.items.length - answered.value} 题未作答，仍要交卷吗？`
        : '交卷后将显示答案和解析。',
    confirmText: '交卷',
    success: ({ confirm }) => {
      if (confirm) submit()
    },
  })
}
async function submit() {
  if (submitting.value || session.value?.status === 'submitted') return
  submitting.value = true
  actionError.value = ''
  clearTimeout(saveTimer)
  try {
    try {
      await flush()
    } catch (e) {
      if (!expired.value) throw e
    }
    const result = await postData(
      `/study-sessions/${id.value}/submit`,
      { version: session.value.version },
      { silent: true, timeout: 180000 },
    )
    session.value = result
    clearInterval(tick)
    saved.value = true
    removeDraft()
    actionError.value = ''
    uni.pageScrollTo({ scrollTop: 0, duration: 150 })
  } catch (e) {
    actionError.value = e.message || '交卷未完成，作答已保留，可以重试'
  } finally {
    submitting.value = false
  }
}
function answerText(value) {
  if (value == null || value === '') return '未作答'
  return Array.isArray(value)
    ? value.join('、')
    : typeof value === 'object'
      ? JSON.stringify(value)
      : String(value)
}
function verdictClass(item) {
  return !item.grading?.can_update_learning
    ? 'pending'
    : item.grading.correct
      ? 'correct'
      : 'incorrect'
}
function verdict(item) {
  return !item.grading?.can_update_learning
    ? '待核对'
    : item.grading.correct
      ? '答对了'
      : hasAnswer(item.student_answer)
        ? '需要订正'
        : '未作答'
}
async function addMistake(item) {
  if (adding.value || added.value.has(item.id)) return
  adding.value = item.id
  actionError.value = ''
  try {
    await postData(
      '/questions/manual',
      {
        question_text: item.question.question_text,
        subject: item.question.subject,
        grade: item.question.grade || item.question.grade_band,
        question_type: normalizeOptions(item.question.options).length
          ? isMultipleChoice(item.question.question_type)
            ? '多选题'
            : '单选题'
          : '综合题',
        options: normalizeOptions(item.question.options).map(({ label, text }) => ({
          label,
          text,
        })),
        student_answer: answerText(item.student_answer),
        student_steps: [],
      },
      { silent: true },
    )
    added.value = new Set([...added.value, item.id])
  } catch (e) {
    actionError.value = e.message || '暂时无法加入错题本'
  } finally {
    adding.value = ''
  }
}
function backToBank() {
  go(`/pages/bank/bank?mode=${session.value.mode}`, { replace: true })
}
onLoad((query) => {
  id.value = query.id || ''
  load()
})
onHide(() => {
  clearTimeout(saveTimer)
  if (!submitting.value) flush().catch(() => {})
})
onUnload(() => {
  disposed = true
  clearTimeout(saveTimer)
  clearInterval(tick)
})
</script>
<style scoped lang="scss">
.study-page {
  max-width: 900px;
}
.exam-clock {
  display: block;
  padding: 7px 12px;
  border-radius: 10px;
  color: #8f4f16;
  background: #fff0da;
  font-size: 16px;
  font-variant-numeric: tabular-nums;
}
.exam-clock.urgent {
  color: var(--color-error);
  background: var(--color-error-soft);
}
.session-toolbar {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  color: var(--color-text-secondary);
  font-size: 14px;
}
.save-status {
  font-size: 12px;
}
.answer-progress {
  height: 5px;
  margin: 16px 0 24px;
  background: #e1e9f1;
  border-radius: 5px;
  overflow: hidden;
}
.answer-progress > view {
  height: 100%;
  background: #278a67;
  transition: width 160ms ease;
}
.question-workspace {
  padding: 28px;
}
.question-category {
  display: flex;
  align-items: center;
  gap: 12px;
  color: var(--color-text-secondary);
  font-size: 12px;
  margin-bottom: 20px;
}
.question-category > text:first-child {
  color: #176cbb;
  background: #edf5ff;
  padding: 3px 9px;
  border-radius: 6px;
}
.question-category > text:last-child {
  margin-left: auto;
}
.question-stem {
  display: block;
  font-size: 18px;
  line-height: 1.8;
}
.question-image {
  display: block;
  width: 100%;
  max-width: 560px;
  margin: 16px 0;
}
.answer-options {
  display: grid;
  gap: 12px;
  margin-top: 28px;
}
.answer-options button {
  display: flex;
  align-items: center;
  gap: 14px;
  width: 100%;
  min-height: 56px;
  padding: 14px 16px;
  margin: 0;
  background: #f6f8fc;
  border: 1px solid transparent;
  border-radius: 14px;
  text-align: left;
  font-size: 16px;
  line-height: 1.6;
}
.answer-options button.selected {
  border-color: #7ab2df;
  background: #edf5ff;
  color: #134f89;
}
.answer-options button :deep(.math-text) {
  flex: 1;
  min-width: 0;
}
.option-letter {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: #fff;
  font-size: 14px;
}
.selected .option-letter {
  color: #fff;
  background: var(--color-primary);
}
.question-navigation {
  display: flex;
  gap: 12px;
  margin-top: 16px;
}
.question-navigation button {
  flex: 1;
  gap: 8px;
  margin: 0;
  font-size: 14px;
}
.question-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin: 28px 0;
}
.question-grid button {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
  width: 40px;
  height: 40px;
  margin: 0;
  padding: 0;
  background: #fff;
  border-radius: 10px;
  font-size: 14px;
  color: var(--color-text-secondary);
  border: 1px solid transparent;
}
.question-grid button.answered {
  background: #e7f4ed;
  color: #226747;
}
.question-grid button.current {
  border-color: var(--color-primary);
  color: var(--color-primary);
}
.submit-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  font-size: 13px;
  color: var(--color-text-secondary);
}
.submit-row .primary-btn {
  margin: 0;
  min-height: 44px;
  font-size: 15px;
  padding: 12px 20px;
}
.result-summary {
  padding: 28px;
  background: #e7f4ed;
  border-radius: 24px;
  margin-bottom: 24px;
}
.result-summary.exam {
  background: #fff0da;
}
.result-title {
  font-size: 18px;
  font-weight: 600;
}
.result-score {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-top: 12px;
}
.result-score > text {
  font-size: 42px;
  font-weight: 650;
  line-height: 1.2;
  color: #226747;
  letter-spacing: -0.04em;
}
.exam .result-score > text {
  color: #8f4f16;
}
.result-score small {
  font-size: 16px;
  color: var(--color-text-secondary);
}
.result-meta {
  display: block;
  font-size: 14px;
  margin-top: 14px;
}
.pending-note {
  display: block;
  font-size: 13px;
  color: var(--color-text-secondary);
  margin-top: 8px;
}
.review-heading {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
  font-size: 14px;
}
.verdict.correct {
  color: #267350;
}
.verdict.incorrect {
  color: var(--color-error);
}
.verdict.pending {
  color: #8f4f16;
}
.review-option {
  display: flex;
  gap: 10px;
  font-size: 14px;
  margin-top: 10px;
  color: var(--color-text-secondary);
}
.review-answers {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-top: 24px;
  padding: 16px;
  background: var(--color-bg);
  border-radius: 12px;
}
.answer-label {
  display: block;
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-bottom: 8px;
}
.reference-solution {
  display: block;
  margin-top: 20px;
}
.grading-feedback {
  display: block;
  margin-top: 16px;
  font-size: 14px;
  color: var(--color-text-secondary);
}
.add-mistake {
  margin-top: 20px;
}
@media (max-width: 390px) {
  .question-workspace {
    padding: 22px;
  }
  .submit-row {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
