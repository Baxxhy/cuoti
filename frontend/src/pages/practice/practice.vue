<template>
  <view class="page practice-workspace">
    <app-header title="类似题练习" back />
    <view class="page-content">
      <view v-if="loading" class="loading-panel">
        <state-panel state="loading" />
        <text class="loading-hint">正在挑选合适练习，首次匹配可能较慢</text>
        <button role="button" class="secondary-btn" @click="go('/pages/bank/bank')">
          去题库选题
        </button>
      </view>
      <view v-else-if="error" class="card empty-card">
        <b>{{ missingTarget ? '先确认这道题的知识点' : '暂时无法开始练习' }}</b>
        <text>{{ error }}</text>
        <button
          role="button"
          v-if="missingTarget"
          class="primary-btn"
          @click="go(`/pages/detail/detail?id=${encodeURIComponent(mistakeId)}`)"
        >
          核对这道错题
        </button>
        <button
          role="button"
          :class="missingTarget ? 'secondary-btn' : 'primary-btn'"
          @click="go('/pages/bank/bank')"
        >
          去题库选题
        </button>
        <button v-if="!missingTarget" role="button" class="secondary-btn" @click="loadQuestion()">
          重新匹配
        </button>
      </view>
      <template v-else-if="question">
        <view class="context-row">
          <text>{{ question.subject }}</text>
          <text>{{ modeLabel }}</text>
        </view>
        <view class="card question-card">
          <text class="source">
            {{ questionTypeLabel(question.question_type) }}
          </text>
          <question-content
            class="question-stem"
            :text="question.stem"
            :images="question.images || []"
          />
          <checkbox-group
            v-if="multiple && options.length"
            @change="setChoices($event.detail.value)"
          >
            <text class="source">多选题，请选出所有符合条件的选项</text>
            <label v-for="option in options" :key="option.label" class="option">
              <checkbox
                :value="option.label"
                :checked="selectedOptions.includes(option.label)"
                :disabled="submitting || !!result"
                color="var(--color-primary)"
              />
              <question-content
                class="option-text"
                :text="`${option.label}. ${option.text}`"
                :images="option.image_urls || []"
                :image-label="`选项${option.label}配图`"
                :previewable="!!result"
              />
            </label>
          </checkbox-group>
          <radio-group v-else-if="options.length" @change="answer = $event.detail.value">
            <label v-for="option in options" :key="option.label" class="option">
              <radio
                :value="option.label"
                :checked="answer === option.label"
                :disabled="submitting || !!result"
                color="var(--color-primary)"
              />
              <question-content
                class="option-text"
                :text="`${option.label}. ${option.text}`"
                :images="option.image_urls || []"
                :image-label="`选项${option.label}配图`"
                :previewable="!!result"
              />
            </label>
          </radio-group>
          <template v-else>
            <written-answer
              ref="writtenAnswer"
              v-model="answer"
              placeholder="写下答案和关键步骤"
              upload-url="/answers/handwriting"
              :upload-data="handwritingContext"
              @handwriting-change="onHandwritingChange"
              @uploading-change="uploadingHandwriting = $event"
            />
          </template>
        </view>
        <view
          v-if="result"
          class="card result-card"
          :class="{ correct: result.correct === true, pending: !result.can_update_learning }"
        >
          <b>{{ resultTitle }}</b>
          <math-text :text="learningFeedback(result.feedback)" inline />
          <question-content
            v-if="result.answer || result.answer_image_urls?.length"
            class="reference"
            :text="`参考答案：${displayAnswer}`"
            :images="result.answer_image_urls || []"
            image-label="答案图"
          />
          <question-content
            v-if="result.solution || result.solution_image_urls?.length"
            class="reference"
            :text="result.solution"
            :images="result.solution_image_urls || []"
            image-label="解析图"
            :inline="false"
          />
          <text v-if="result.mastery !== undefined && result.mastery !== null">
            掌握状态：{{ Math.round(result.mastery_before * 100) }}% →
            {{ Math.round(result.mastery * 100) }}%
          </text>
          <text v-else-if="!result.can_update_learning">本次作答已保存，暂不更新掌握情况。</text>
        </view>
        <button
          v-if="!result"
          role="button"
          class="primary-btn"
          :disabled="!answer.trim() || submitting || uploadingHandwriting"
          :aria-disabled="!answer.trim() || submitting || uploadingHandwriting"
          @click="submit"
        >
          {{ submitting ? '正在判定…' : uploadingHandwriting ? '正在解析手写答案…' : '提交答案' }}
        </button>
        <button v-else role="button" class="primary-btn" @click="nextQuestion">再练一道</button>
        <button
          role="button"
          v-if="result && !result.can_update_learning"
          class="secondary-btn switch-mode"
          @click="result = null"
        >
          修改后重新提交
        </button>
        <button role="button" v-if="result" class="secondary-btn switch-mode" @click="switchMode">
          {{ mode === 'reinforce' ? '换个问法试试' : '再做一道类似的' }}
        </button>
      </template>
      <button
        aria-label="学习安排"
        v-if="mistakeId"
        class="disclosure-link"
        role="button"
        tabindex="0"
        @click="go(`/pages/repair/repair?id=${mistakeId}`)"
        @keydown.enter.prevent="go(`/pages/repair/repair?id=${mistakeId}`)"
      >
        学习安排
        <uni-icons aria-hidden="true" type="right" size="18" />
      </button>
    </view>
  </view>
</template>

<script setup>
import { learningFeedback } from '@/utils/learning-feedback.js'
import MathText from '@/components/math-text/math-text.vue'
import QuestionContent from '@/components/question-content/question-content.vue'
import WrittenAnswer from '@/components/written-answer/written-answer.vue'

import { computed, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { postData } from '@/api/index.js'
import { go } from '@/utils/navigation.js'
import {
  choiceAnswer,
  isMultipleChoice,
  normalizeOptions,
  questionTypeLabel,
} from '@/utils/question.js'
const mistakeId = ref(''),
  mode = ref('reinforce'),
  question = ref(null),
  answer = ref(''),
  result = ref(null),
  loading = ref(false),
  submitting = ref(false),
  error = ref(''),
  missingTarget = ref(false)
const writtenAnswer = ref(null),
  handwritingImage = ref(''),
  handwritingRecognition = ref(null),
  uploadingHandwriting = ref(false)
const selectedOptions = ref([]),
  startedAt = ref(Date.now())
const options = computed(() => normalizeOptions(question.value?.options))
const multiple = computed(() => isMultipleChoice(question.value?.question_type))
function setChoices(values) {
  selectedOptions.value = values
  answer.value = choiceAnswer(values, question.value?.options)
}
const modeLabel = computed(() => (mode.value === 'reinforce' ? '再做一道类似的' : '换个问法试试'))
const displayAnswer = computed(() =>
  typeof result.value?.answer === 'string'
    ? result.value.answer
    : JSON.stringify(result.value?.answer),
)
const resultTitle = computed(() => {
  if (!result.value?.can_update_learning)
    return result.value?.verdict === 'probably_correct' ? '答案还需核对' : '结果待核对'
  return result.value?.correct ? '答对了' : '答案还不正确'
})
const handwritingContext = computed(() => ({
  context_type: 'practice',
  context_id: question.value?.question_id || '',
  mistake_id: mistakeId.value,
  mode: mode.value,
}))
function resetHandwriting() {
  writtenAnswer.value?.reset()
  handwritingImage.value = ''
  handwritingRecognition.value = null
}
function onHandwritingChange(value) {
  handwritingImage.value = value.image_url || ''
  handwritingRecognition.value = value.recognition || null
}
async function loadQuestion(forceNew = false) {
  if (loading.value) return
  loading.value = true
  error.value = ''
  missingTarget.value = false
  answer.value = ''
  selectedOptions.value = []
  result.value = null
  resetHandwriting()
  try {
    question.value = await postData(
      '/practice/recommend',
      { mistake_id: mistakeId.value, mode: mode.value, force_new: forceNew },
      { timeout: 300000, silent: true },
    )
    startedAt.value = Date.now()
  } catch (exc) {
    question.value = null
    missingTarget.value = exc?.statusCode === 422
    error.value = exc?.message || '暂时无法匹配练习，请重试或去题库选题。'
  } finally {
    loading.value = false
  }
}
async function submit() {
  if (submitting.value || !answer.value.trim()) return
  submitting.value = true
  try {
    result.value = await postData('/practice/attempt', {
      question_id: question.value.question_id,
      student_answer: answer.value,
      mistake_id: mistakeId.value,
      mode: mode.value,
      duration_seconds: Math.max(1, Math.round((Date.now() - startedAt.value) / 1000)),
      handwriting_image_url: handwritingImage.value,
      handwriting_recognition: handwritingRecognition.value,
    })
  } catch (exc) {
    if (exc?.statusCode === 409) error.value = exc.message || '学习目标已变化，请重新匹配练习'
  } finally {
    submitting.value = false
  }
}
function nextQuestion() {
  loadQuestion(true)
}
function switchMode() {
  mode.value = mode.value === 'reinforce' ? 'variation' : 'reinforce'
  loadQuestion(true)
}
onLoad((query) => {
  mistakeId.value = query.id
  mode.value = query.mode === 'variation' ? 'variation' : 'reinforce'
  loadQuestion()
})
</script>

<style scoped lang="scss">
.loading-panel {
  text-align: center;
}
.loading-hint {
  display: block;
  color: var(--color-text-secondary);
  font-size: 25rpx;
  line-height: 1.6;
}
.context-row {
  display: flex;
  gap: 12rpx;
  margin-bottom: 18rpx;
}
.context-row text {
  padding: 8rpx 14rpx;
  border: 1rpx solid var(--color-border);
  border-radius: 999rpx;
  color: var(--color-text-secondary);
  font-size: 21rpx;
}
.question-card .source {
  display: block;
  color: var(--color-text-secondary);
  font-size: 21rpx;
  margin-bottom: 12rpx;
}
.question-stem {
  font-size: 32rpx;
  line-height: 1.7;
  font-weight: 500;
}
.question-card image {
  width: 100%;
  margin-top: 18rpx;
}
.option {
  display: flex;
  align-items: center;
  gap: 12rpx;
  padding: 18rpx 0;
  border-bottom: 1rpx solid var(--color-border);
  font-size: 30rpx;
  min-height: 88rpx;
  box-sizing: border-box;
}
.option-text {
  flex: 1;
  line-height: 1.6;
}
.option :deep(.content-image) {
  max-width: 180px;
}
.question-card :deep(.written-answer) {
  display: block;
  margin-top: 22rpx;
}
.result-card {
  margin-top: 20rpx;
  background: var(--color-warning-soft);
}
.result-card.correct {
  background: var(--color-success-soft);
}
.result-card.pending {
  background: var(--color-surface-subtle);
}
.result-card b,
.result-card text {
  display: block;
}
.result-card b {
  font-size: 28rpx;
}
.result-card text {
  margin-top: 10rpx;
  color: var(--color-text-secondary);
  line-height: 1.6;
}
.reference {
  margin-top: 10rpx;
  color: var(--color-text-primary) !important;
  line-height: 1.6;
}
.switch-mode {
  margin-top: 14rpx;
}
.empty-card {
  text-align: left;
  padding: 20px;
}
.empty-card b {
  font-size: 17px;
  font-weight: 500;
}
.empty-card .primary-btn,
.empty-card .secondary-btn {
  min-height: 44px;
  margin-top: 12px;
  font-size: 15px;
}
.empty-card b,
.empty-card text {
  display: block;
}
.empty-card text {
  font-size: 14px;
  line-height: 1.6;
  margin: 12rpx 0 22rpx;
  color: var(--color-text-secondary);
}
</style>
