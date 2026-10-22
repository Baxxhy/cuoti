<template>
  <view class="page diagnosis-page">
    <app-header :title="hasStudentWork ? '错因诊断' : '本题解析'" back />

    <!-- 加载 / 错误 -->
    <state-panel
      v-if="!item"
      :state="!id || error ? 'error' : 'loading'"
      :message="!id ? '请先选择一道错题' : undefined"
      :retry-text="!id ? '选择错题' : '重新加载'"
      @retry="id ? load() : go('/pages/problem/list')"
    />

    <view v-else class="page-content">
      <text v-if="entryError" class="account-notice" role="alert">{{ entryError }}</text>
      <text v-if="repairEvidenceNotice" class="evidence-caption" role="status">
        {{ repairEvidenceNotice }}
      </text>
      <view v-if="evidenceSummary" class="summary-card">
        <text class="summary-kicker">
          {{ evidenceSummary.title }}
        </text>
        <math-text :text="evidenceSummary.reason" />
        <text v-if="evidenceSummary.question" class="status-message">
          {{ evidenceSummary.question }}
        </text>
      </view>
      <!-- =====================================================
           已有诊断
      ====================================================== -->
      <view
        v-if="generating || generationError"
        class="empty-card"
        role="status"
        aria-live="polite"
      >
        <text class="empty-title">
          {{ generating ? (hasStudentWork ? '正在分析错因' : '正在生成本题解析') : '分析未完成' }}
        </text>
        <text class="empty-desc">
          {{ generating ? '分析完成后会自动展示结果，请稍候。' : generationError }}
        </text>
        <button v-if="!generating" role="button" class="primary-btn" @click="generate">
          重新分析
        </button>
      </view>
      <template v-else-if="diagnosis && hasStudentWork">
        <!-- 仅有选择答案时，不能凭空编造学生的解题步骤。 -->
        <template v-if="diagnosisState.kind !== 'finding'">
          <view class="summary-card">
            <text class="summary-kicker">本次诊断</text>
            <text class="summary-title">{{ diagnosisState.title }}</text>
            <text class="status-message">{{ diagnosisState.message }}</text>
          </view>
          <button
            class="primary-btn tutor-btn"
            :aria-disabled="busy"
            role="button"
            tabindex="0"
            :disabled="busy"
            @click="continueFromSummary"
            @keydown.enter.prevent="continueFromSummary"
            @keydown.space.prevent
            @keyup.space.prevent="continueFromSummary"
          >
            {{ busy ? '正在准备…' : diagnosisState.kind === 'clear' ? '重新作答' : '查看相关知识' }}
          </button>
          <button
            v-if="diagnosisState.kind === 'clear'"
            class="secondary-btn"
            role="button"
            tabindex="0"
            @click="openKnowledgeGraph"
            @keydown.enter.prevent="openKnowledgeGraph"
          >
            查看相关知识
          </button>
          <button
            role="button"
            class="secondary-btn"
            :aria-expanded="showPath"
            @click="showPath = !showPath"
          >
            {{ showPath ? '收起参考过程' : '查看参考过程' }}
          </button>
          <view v-if="showPath" class="solution-card">
            <view v-for="(step, index) in solutionSteps" :key="index" class="solution-step">
              <text>{{ index + 1 }}</text>
              <math-text :text="step" />
            </view>
          </view>
        </template>
        <template v-else-if="isChoiceAnswerOnly">
          <view class="answer-summary-card">
            <view class="answer-row">
              <text class="answer-label">你的作答</text>
              <math-text class="answer-value" :text="studentAnswer" inline />
            </view>
            <view class="answer-row correct-answer-row">
              <text class="answer-label">正确答案</text>
              <math-text
                class="answer-value correct-answer"
                :text="finalAnswer || '待确认'"
                inline
              />
            </view>
          </view>

          <view class="section-title">
            <text>{{ focusOptionLabel }} 选项分析</text>
          </view>
          <view class="reason-card">
            <math-text class="option-quote" :text="focusOptionText" />
            <text class="analysis-lead">可能错因</text>
            <math-text
              v-for="(line, index) in choiceReasonLines"
              :key="index"
              class="reason-text"
              :text="line"
            />
          </view>

          <view class="section-title">
            <text>正确答案与判断依据</text>
          </view>
          <view class="thought-card correct-thought">
            <view class="thought-mark">
              <uni-icons
                aria-hidden="true"
                :type="modelReviewPending ? 'help' : 'checkmarkempty'"
                size="20"
                color="var(--color-primary)"
              />
            </view>
            <math-text class="thought-text" :text="choiceCorrection" />
          </view>

          <button
            class="primary-btn tutor-btn"
            :aria-disabled="busy"
            role="button"
            tabindex="0"
            :disabled="busy"
            @click="startLearning"
            @keydown.enter.prevent="startLearning"
            @keydown.space.prevent
            @keyup.space.prevent="startLearning"
          >
            {{ busy ? '正在准备…' : '开始订正' }}
          </button>

          <text class="more-label">补充信息</text>
          <view class="secondary-area">
            <view class="secondary-row" @click="showPath = !showPath">
              <view><text class="secondary-title">查看完整解题过程</text></view>
              <uni-icons
                aria-hidden="true"
                :type="showPath ? 'top' : 'bottom'"
                size="18"
                color="var(--color-text-tertiary)"
              />
            </view>
            <view v-if="showPath" class="path-section">
              <view class="path-list">
                <view v-for="(step, index) in solutionSteps" :key="index" class="step-row">
                  <view class="step-number">{{ index + 1 }}</view>
                  <math-text class="step-content" :text="step" />
                </view>
              </view>
            </view>
            <view class="secondary-row detail-row" @click="showDetails = !showDetails">
              <view><text class="secondary-title">查看 AI 判断依据</text></view>
              <uni-icons
                aria-hidden="true"
                :type="showDetails ? 'top' : 'bottom'"
                size="18"
                color="var(--color-text-tertiary)"
              />
            </view>
            <view v-if="showDetails" class="detail-panel">
              <view class="detail-item">
                <text class="detail-label">你的问题</text>
                <text class="detail-value">{{ errorTypeLabel(diagnosis.error_type) }}</text>
              </view>
              <view class="detail-item">
                <text class="detail-label">
                  {{ diagnosis.user_confirmed ? '当前诊断说明' : 'AI 说明' }}
                </text>
                <math-text
                  class="detail-value"
                  :text="diagnosis.root_misconception || '正在根据题目条件核对。'"
                />
              </view>
            </view>
          </view>
        </template>

        <template v-else>
          <!-- 1. 最核心结论 -->
          <view class="summary-card">
            <text class="summary-kicker">诊断提示</text>
            <text class="summary-title">
              {{ firstErrorStepNumber ? `第 ${firstErrorStepNumber} 步` : '本次作答' }}：{{
                errorFocus
              }}
            </text>
          </view>

          <view class="section-title">
            <text>
              {{
                analysisMode === 'calculation' || analysisMode === 'comprehensive'
                  ? '关键步骤'
                  : '你的作答依据'
              }}
            </text>
          </view>

          <view class="thought-card student-thought">
            <view class="thought-mark">
              <uni-icons
                aria-hidden="true"
                type="closeempty"
                size="20"
                color="var(--color-error)"
              />
            </view>
            <math-text class="thought-text" :text="studentThought" />
          </view>

          <view class="section-title">
            <text>{{ diagnosis.user_confirmed ? '当前诊断说明' : 'AI 分析' }}</text>
          </view>

          <view class="reason-card">
            <math-text
              v-for="(line, index) in reasonLines"
              :key="index"
              class="reason-text"
              :text="line"
            />
          </view>

          <view class="section-title">
            <text>
              {{
                manualReferencePending
                  ? '这一步还需核对'
                  : modelReviewPending
                    ? '参考修正（待核对）'
                    : analysisMode === 'fill'
                      ? '正确答案'
                      : analysisMode === 'calculation'
                        ? '这一步应该怎么改'
                        : '正确判断'
              }}
            </text>
          </view>

          <view class="thought-card correct-thought">
            <view class="thought-mark">
              <uni-icons
                aria-hidden="true"
                :type="manualReferencePending || modelReviewPending ? 'help' : 'checkmarkempty'"
                size="20"
                color="var(--color-primary)"
              />
            </view>
            <math-text class="thought-text" :text="correctThought" />
          </view>

          <!-- 主行动 -->
          <button
            class="primary-btn tutor-btn"
            :aria-disabled="busy"
            role="button"
            tabindex="0"
            :disabled="busy"
            @click="startLearning"
            @keydown.enter.prevent="startLearning"
            @keydown.space.prevent
            @keyup.space.prevent="startLearning"
          >
            {{ busy ? '正在准备…' : '开始订正' }}
          </button>

          <!-- =====================================================
             次要内容：默认折叠
        ====================================================== -->

          <text class="more-label">补充信息</text>
          <view class="secondary-area">
            <!-- 查看路径 -->
            <view class="secondary-row" @click="showPath = !showPath">
              <view>
                <text class="secondary-title">我的解题过程</text>
              </view>

              <uni-icons
                aria-hidden="true"
                :type="showPath ? 'top' : 'bottom'"
                size="18"
                color="var(--color-text-tertiary)"
              />
            </view>

            <!-- 路径对比展开 -->
            <view v-if="showPath" class="path-section">
              <view class="segmented">
                <view :class="{ active: tab === 'student' }" @click.stop="tab = 'student'">
                  我的步骤
                </view>

                <view :class="{ active: tab === 'reference' }" @click.stop="tab = 'reference'">
                  参考步骤
                </view>
              </view>

              <view class="path-list">
                <view
                  v-for="(step, index) in currentSteps"
                  :key="step.id || index"
                  class="step-row"
                  :class="{
                    first: tab === 'student' && index === diagnosis.first_error_step,
                  }"
                >
                  <view class="step-number">
                    {{ index + 1 }}
                  </view>

                  <view class="step-main">
                    <view class="step-head">
                      <math-text
                        class="step-content"
                        :text="step.formula || step.expression || step.text || '未识别到内容'"
                      />

                      <text
                        v-if="tab === 'student' && index === diagnosis.first_error_step"
                        class="first-tag"
                      >
                        从这里开始
                      </text>
                    </view>

                    <text class="step-caption">
                      {{ stepCaption(step, index) }}
                    </text>

                    <text
                      v-if="tab === 'student' && evidenceAt(index)?.propagated"
                      class="propagated-text"
                    >
                      后面的结果可能受到前面错误影响
                    </text>
                  </view>
                </view>

                <view v-if="!currentSteps.length" class="empty-path">暂时没有可展示的步骤</view>
              </view>
            </view>

            <!-- 查看诊断详情 -->
            <view class="secondary-row detail-row" @click="showDetails = !showDetails">
              <view>
                <text class="secondary-title">AI 判断依据</text>
              </view>

              <uni-icons
                aria-hidden="true"
                :type="showDetails ? 'top' : 'bottom'"
                size="18"
                color="var(--color-text-tertiary)"
              />
            </view>

            <!-- 诊断详情 -->
            <view v-if="showDetails" class="detail-panel">
              <view class="detail-item">
                <text class="detail-label">错误类型</text>

                <text class="detail-value">
                  {{ errorTypeLabel(diagnosis.error_type) }}
                </text>
              </view>

              <view class="detail-item">
                <text class="detail-label">错误位置</text>

                <text class="detail-value">
                  {{ diagnosis.error_location || '作答过程' }}
                </text>
              </view>

              <view v-if="diagnosis.first_error_text" class="detail-item">
                <text class="detail-label">原步骤</text>

                <math-text class="detail-value" :text="diagnosis.first_error_text" />
              </view>

              <view v-if="diagnosis.propagated_errors?.length" class="detail-item">
                <text class="detail-label">后续影响</text>

                <math-text class="detail-value" :text="diagnosis.propagated_errors.join('；')" />
              </view>
            </view>

            <view class="secondary-row detail-row" @click="openKnowledgeGraph">
              <view><text class="secondary-title">知识关联</text></view>
              <uni-icons
                aria-hidden="true"
                type="right"
                size="18"
                color="var(--color-text-tertiary)"
              />
            </view>
          </view>
        </template>
        <!-- =====================================================
             人工修正
        ====================================================== -->
        <view v-if="editing" class="correction-card">
          <view class="correction-head">
            <text class="correction-title">修正诊断</text>

            <text class="correction-cancel" @click="editing = false">取消</text>
          </view>

          <view class="two-column">
            <view class="field">
              <text class="field-label">第几步开始出错</text>

              <input
                v-model.number="correction.first_error_step"
                type="number"
                min="1"
                :max="item.student_steps?.length || undefined"
                placeholder="未定位时留空"
                class="field-input"
              />
              <text class="muted">从第1步开始计数；尚未定位可留空。</text>
            </view>

            <view class="field">
              <text class="field-label">错误类型</text>

              <picker
                :range="errorLabels"
                @change="correction.error_type = errorCodes[$event.detail.value]"
              >
                <view class="field-picker">
                  {{ errorTypeLabel(correction.error_type) }}
                </view>
              </picker>
            </view>
          </view>

          <view class="field">
            <text class="field-label">出错位置说明</text>

            <input v-model="correction.error_location" class="field-input" />
          </view>

          <view class="field">
            <text class="field-label">真正原因</text>

            <textarea v-model="correction.root_misconception" class="field-textarea" />
          </view>

          <view class="field">
            <text class="field-label">建议讲法</text>

            <textarea v-model="correction.recommended_strategy" class="field-textarea" />
          </view>

          <text v-if="correctionError" class="account-notice" role="alert">
            {{ correctionError }}
          </text>
          <button role="button" class="primary-btn" :disabled="busy" @click="saveCorrection">
            {{ busy ? '正在保存…' : '保存修正' }}
          </button>
        </view>

        <!-- 反馈入口 -->
        <text v-if="!editing" class="feedback-link" @click="beginEdit">诊断结果不对？告诉我</text>
      </template>

      <template v-else-if="solutionAvailable">
        <view class="solution-intro">
          <text class="solution-kicker">还没有你的作答过程</text>
          <text class="solution-title">先看这道题怎么做</text>
          <text class="solution-desc">完成作答后，AI 才能根据你的实际思路判断错因。</text>
        </view>

        <view class="section-title"><text>解题思路</text></view>
        <view class="solution-card">
          <view v-for="(step, index) in solutionSteps" :key="index" class="solution-step">
            <text>{{ index + 1 }}</text>
            <math-text :text="step" />
          </view>
        </view>

        <view v-if="finalAnswer" class="answer-card">
          <text>答案</text>
          <math-text :text="finalAnswer" />
        </view>

        <button
          class="primary-btn tutor-btn"
          role="button"
          tabindex="0"
          :disabled="busy"
          @click="startLearning"
          @keydown.enter.prevent="startLearning"
          @keydown.space.prevent
          @keyup.space.prevent="startLearning"
        >
          跟着 AI 学这道题
        </button>
      </template>

      <view v-else class="empty-card">
        <text class="empty-title">{{ item.confirmed ? '尚未生成解析' : '请先确认题目' }}</text>
        <text class="empty-desc">
          {{
            item.confirmed
              ? '重新分析后，会在这里展示结果。'
              : '核对题干与作答并保存后，即可开始分析。'
          }}
        </text>
        <button
          role="button"
          class="primary-btn"
          :disabled="busy"
          @click="item.confirmed ? generate() : go(`/pages/ocr/ocr?id=${id}`)"
        >
          {{ item.confirmed ? '重新分析' : '核对题目' }}
        </button>
      </view>
      <button
        aria-label="错因回放"
        role="button"
        tabindex="0"
        v-if="diagnosis && hasStudentWork"
        class="disclosure-link"
        @keydown.enter.prevent="go(`/pages/replay/replay?id=${id}`)"
        @keydown.space.prevent
        @keyup.space.prevent="go(`/pages/replay/replay?id=${id}`)"
        @click="go(`/pages/replay/replay?id=${id}`)"
      >
        错因回放
        <uni-icons aria-hidden="true" type="right" size="18" />
      </button>
    </view>
  </view>
</template>

<script setup>
import MathText from '@/components/math-text/math-text.vue'
import { computed, reactive, ref } from 'vue'

import { onLoad, onShow, onHide, onUnload } from '@dcloudio/uni-app'

import { getData, patchData, postData } from '@/api/index.js'

import { ERROR_TYPE_LABELS, errorTypeLabel } from '@/constants/education.js'

import { go } from '@/utils/navigation.js'
import {
  diagnosisView,
  diagnosisReason,
  diagnosisEvidenceView,
  choiceCorrectionText,
} from '@/utils/diagnosis.js'
import { requestLearningTask } from '@/utils/task-entry.js'

/* =========================================================
   基础状态
========================================================= */

const id = ref('')

const item = ref(null)

const error = ref(false)

const tab = ref('student')

const editing = ref(false)
const correctionError = ref('')

const busy = ref(false)
const generating = ref(false)
const generationError = ref('')
const entryError = ref('')
let active = false,
  revision = 0

const showPath = ref(false)

const showDetails = ref(false)

const verifying = ref(false)

/* =========================================================
   人工修正
========================================================= */

const correction = reactive({
  first_error_step: '',
  error_type: 'unknown',
  root_misconception: '',
  error_location: '',
  recommended_strategy: '',
})

/* =========================================================
   数据
========================================================= */

const diagnosis = computed(() => item.value?.diagnosis)
const diagnosisState = computed(() => diagnosisView(item.value))
const evidenceSummary = computed(() => diagnosisEvidenceView(item.value))
const repairEvidenceNotice = computed(() => {
  const evidence = diagnosis.value?.counterfactual
  if (evidence?.stale_after_correction) return '错因已修改，请重新核对订正建议。'
  if (evidence?.legacy_review_required) return '这是之前的订正建议，请结合原题核对。'
  if (evidence?.verification_method === 'qwen_proposal_requires_review')
    return '以下是 AI 建议，尚未验证是否正确，请对照原题核对。'
  if (evidence?.preserved_prefix === false)
    return '建议中改动了你前面正确的步骤，请对照原作答核对。'
  if (evidence?.reference_consistent && !evidence.root_cause_confirmed)
    return '订正建议与参考解法一致，但错因仍需你确认。'
  return ''
})

const analysisMode = computed(() => {
  const type = String(item.value?.question_type || '').toLowerCase()
  if (/选择|choice|multiple/.test(type)) return 'choice'
  if (/填空|fill/.test(type)) return 'fill'
  if (/计算|解答|calculation/.test(type)) return 'calculation'
  return 'comprehensive'
})

const hasStudentWork = computed(() => {
  const answer = String(item.value?.student_answer || '').trim()
  const steps = item.value?.student_steps || []
  return Boolean(
    answer ||
      steps.some((step) => String(step.text || step.formula || step.expression || '').trim()),
  )
})

const hasStudentSteps = computed(() =>
  (item.value?.student_steps || []).some((step) => {
    const text = String(step.text || step.formula || step.expression || '').trim()
    // 选择题的选项字母是答案，不是学生解题草稿。
    return Boolean(text) && !/^[A-Z](?:\s*[、,，]\s*[A-Z])*$/i.test(text)
  }),
)

const choiceOptions = computed(() =>
  (item.value?.options || [])
    .map((option, index) => ({
      label: String(option.label || option.key || String.fromCharCode(65 + index)).toUpperCase(),
      text: String(option.text || option.content || option.value || '').trim(),
    }))
    .filter((option) => option.label),
)

function answerLabels(value) {
  const known = choiceOptions.value.map((option) => option.label)
  return [
    ...new Set(
      (
        String(value || '')
          .toUpperCase()
          .match(/[A-Z]/g) || []
      ).filter((label) => known.includes(label)),
    ),
  ]
}

const studentAnswer = computed(() => {
  const savedAnswer = String(item.value?.student_answer || '').trim()
  if (savedAnswer) return savedAnswer.toUpperCase()
  if (!choiceOptions.value.length) return ''

  const choiceOnlySteps = (item.value?.student_steps || [])
    .map((step) => String(step.text || step.formula || step.expression || '').trim())
    .filter(Boolean)
  if (choiceOnlySteps.length !== 1) return ''

  const labels = answerLabels(choiceOnlySteps[0])
  return labels.length && /^[A-Z](?:\s*[、,，]\s*[A-Z])*$/i.test(choiceOnlySteps[0])
    ? labels.join('、')
    : ''
})
const selectedOptionLabels = computed(() => answerLabels(studentAnswer.value))
const correctOptionLabels = computed(() => answerLabels(finalAnswer.value))
const isChoiceAnswerOnly = computed(() =>
  Boolean(
    !hasStudentSteps.value &&
      choiceOptions.value.length &&
      selectedOptionLabels.value.length &&
      correctOptionLabels.value.length,
  ),
)
const wrongOptionLabels = computed(() =>
  selectedOptionLabels.value.filter((label) => !correctOptionLabels.value.includes(label)),
)
const missedOptionLabels = computed(() =>
  correctOptionLabels.value.filter((label) => !selectedOptionLabels.value.includes(label)),
)
const focusOptionLabel = computed(
  () =>
    wrongOptionLabels.value[0] ||
    missedOptionLabels.value[0] ||
    selectedOptionLabels.value[0] ||
    '',
)
const focusOption = computed(() =>
  choiceOptions.value.find((option) => option.label === focusOptionLabel.value),
)
const focusOptionText = computed(() => {
  const option = focusOption.value
  return option?.text ? `${option.label}. ${option.text}` : `${option?.label || ''} 选项`
})

const solutionSteps = computed(() =>
  (item.value?.reference_steps || [])
    .map((step) => String(step.text || step.formula || step.expression || step || '').trim())
    .filter(Boolean),
)

const finalAnswer = computed(() => {
  return String(item.value?.analysis?.final_answer || '').trim()
})

const solutionAvailable = computed(
  () => solutionSteps.value.length > 0 || Boolean(finalAnswer.value),
)

const currentSteps = computed(() => {
  if (tab.value === 'student') {
    return item.value?.student_steps || []
  }

  return item.value?.reference_steps || []
})

const firstErrorStepNumber = computed(() => {
  return diagnosisState.value.step
})

/* =========================================================
   学生看到的核心结论

   first_error_text 有时只是原始步骤文本，
   root_misconception 往往更接近真正问题。
========================================================= */

const knowledgeFocus = computed(() => {
  const prerequisite = diagnosis.value?.missing_prerequisites?.find((value) =>
    String(value || '').trim(),
  )
  const knowledge = item.value?.knowledge_points?.find((value) => String(value || '').trim())
  return conciseText(prerequisite || knowledge, '这一步用到的知识点', 24)
})

const errorFocus = computed(() => {
  const type = diagnosis.value?.error_type
  if (type && !['unknown', 'exact', 'equivalent'].includes(type) && ERROR_TYPE_LABELS[type])
    return errorTypeLabel(type)
  const location = String(diagnosis.value?.error_location || '').trim()
  const isGenericLocation = !location || /学生路径|作答过程|第\s*\d+\s*步/.test(location)
  if (!isGenericLocation) return conciseText(location, knowledgeFocus.value, 24)
  if (/集合.*确定性|确定性.*集合/.test(knowledgeFocus.value)) return '判断集合是否成立'
  return `判断${knowledgeFocus.value}`
})

const firstEvidence = computed(() => {
  const entries = diagnosis.value?.evidence || []
  if (diagnosis.value?.user_confirmed) {
    const step = item.value?.student_steps?.[diagnosis.value.first_error_step]
    return step?.id
      ? entries.find(
          (entry) => (entry.metadata_json?.student_step_id || entry.student_step_id) === step.id,
        ) || null
      : null
  }
  return (
    entries.find((entry) => entry.is_first_error) ||
    (diagnosisState.value.step ? entries[diagnosisState.value.step - 1] : null) ||
    null
  )
})

const studentThought = computed(() => {
  const index = diagnosis.value?.first_error_step
  const recorded = Number.isInteger(index) ? item.value?.student_steps?.[index]?.text : ''
  if (String(recorded || '').trim()) return recorded
  const step = String(diagnosis.value?.first_error_text || '').trim()
  return step || String(item.value?.student_answer || '').trim() || '请结合本次作答核对。'
})

const verifiedRepairText = computed(() => {
  const repair = diagnosis.value?.counterfactual
  return repair?.root_cause_confirmed &&
    !repair.stale_after_correction &&
    !repair.legacy_review_required
    ? String(repair.corrected_step || '').trim()
    : ''
})

const manualReference = computed(() => {
  const evidence = { ...firstEvidence.value, ...firstEvidence.value?.metadata_json }
  return item.value?.reference_steps?.find(
    (step) =>
      evidence.reference_step_id &&
      step.id === evidence.reference_step_id &&
      String(step.text || '').trim(),
  )
})

const manualReferencePending = computed(() =>
  Boolean(diagnosis.value?.user_confirmed && !verifiedRepairText.value && !manualReference.value),
)
const modelReviewPending = computed(() => {
  const repair = diagnosis.value?.counterfactual
  return Boolean(
    repair &&
      !verifiedRepairText.value &&
      (repair.verification_method === 'qwen_proposal_requires_review' ||
        repair.legacy_review_required ||
        repair.stale_after_correction ||
        repair.preserved_prefix === false),
  )
})

const correctThought = computed(() => {
  if (verifiedRepairText.value) return verifiedRepairText.value
  if (!hasStudentSteps.value && finalAnswer.value)
    return `参考答案：${finalAnswer.value}。${diagnosis.value?.recommended_strategy || ''}`
  const evidence = { ...firstEvidence.value, ...firstEvidence.value?.metadata_json }
  if (diagnosis.value?.user_confirmed) {
    return manualReference.value?.text || '暂无与你标记步骤对应的参考，请结合原题重新核对。'
  }
  if (evidence.verification_scope && !evidence.reference_step_id)
    return diagnosis.value?.recommended_strategy || '结合原题条件，核对完整答案。'
  const reference =
    evidence.reference_text ||
    (diagnosisState.value.step
      ? item.value?.reference_steps?.[diagnosisState.value.step - 1]?.text
      : '')
  if (reference) return reference
  if (diagnosis.value?.recommended_strategy) return diagnosis.value.recommended_strategy
  if (/集合.*确定性|确定性.*集合/.test(knowledgeFocus.value))
    return '集合中的元素必须可以明确判断。'
  return `${knowledgeFocus.value}需要先理解清楚，再继续计算。`
})

const choiceReasonLines = computed(() => {
  const reason = diagnosisReason(item.value).replace(/\s+/g, ' ').trim()
  if (reason && !/没有完整说明|规则还没有掌握牢|需要重新检查/.test(reason)) {
    return reason
      .split(/[。；;！!]/)
      .map((line) => line.trim())
      .filter(Boolean)
  }
  const reference = solutionSteps.value.find((step) =>
    new RegExp(`(?:选项)?${focusOptionLabel.value}[^。；;]*`).test(step),
  )
  if (reference)
    return [`根据题目条件核对 ${focusOptionLabel.value}：${conciseText(reference, '', 78)}`]
  return [`请根据题目条件重新核对 ${focusOptionLabel.value}，它与正确答案不一致。`]
})

const choiceCorrection = computed(() => {
  return choiceCorrectionText(item.value, correctOptionLabels.value)
})

const reasonLines = computed(() => {
  const raw = diagnosisReason(item.value).replace(/\s+/g, ' ').trim()
  if (!raw) return ['这一步的规则还没有掌握牢。']

  const misconception = raw.match(/^对(.+?)理解不深[，,]\s*误以为(.+?)[。.]?$/)
  if (misconception) {
    const mistakenIdea = misconception[2].replace(
      /^模糊描述也能构成集合$/,
      '模糊描述当成了确定条件',
    )
    return [`你把${mistakenIdea}。`, `${misconception[1]}需要明确判断。`]
  }

  return raw
    .split(/[。；;！!]/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => `${line}。`)
})

const repairTips = computed(() => {
  if (/集合.*确定性|确定性.*集合/.test(knowledgeFocus.value)) {
    return [
      '先问自己：这个对象能不能被明确判断？',
      '能 → 可以组成集合；不能 → 不能组成集合。',
      '马上练习：3 道类似题巩固。',
    ]
  }
  return [
    `先确认：这一步依据的是哪条规则？`,
    `再检查：${knowledgeFocus.value}是否满足题目条件。`,
    '马上练习：3 道类似题巩固。',
  ]
})

function conciseText(value, fallback, limit = 42) {
  const source = String(value || '')
  if (/[$\\]/.test(source)) return source || fallback
  const text = source.replace(/\s+/g, ' ').trim()
  if (!text) return fallback
  const firstSentence = text.split(/[。；;！!]/)[0].trim()
  return firstSentence.length > limit ? `${firstSentence.slice(0, limit)}…` : firstSentence
}

/* =========================================================
   错误类型
========================================================= */

const errorCodes = Object.keys(ERROR_TYPE_LABELS)

const errorLabels = errorCodes.map(errorTypeLabel)

/* =========================================================
   路径证据
========================================================= */

function evidenceAt(index) {
  return diagnosis.value?.evidence?.[index]
}

function stepCaption(step, index) {
  if (tab.value === 'reference') {
    return step.explanation || '参考思路'
  }

  const evidence = evidenceAt(index)

  if (evidence?.alignment === 'branch_solution') return '这个分支的解成立'

  if (index === diagnosis.value?.first_error_step) {
    return '这里开始和正确思路不同'
  }

  if (evidence?.equivalent) {
    return '这一步没有问题'
  }

  if (evidence?.propagated) {
    return '受到前面错误影响'
  }

  return '这一步需要再确认'
}

/* =========================================================
   加载
========================================================= */

async function load(autoGenerate = true) {
  if (!active || !id.value) return
  const current = ++revision,
    questionId = id.value
  error.value = false
  entryError.value = ''
  item.value = null
  try {
    const next = await getData(`/questions/${questionId}`)
    if (!active || current !== revision) return
    item.value = next
    const needsAnalysis =
      next?.confirmed && (hasStudentWork.value ? !next.diagnosis : !solutionAvailable.value)
    if (needsAnalysis) {
      if (autoGenerate && !generationError.value) await generate()
      else if (!autoGenerate) generationError.value = '分析结果暂未就绪，请重新分析。'
      return
    }
    generationError.value = ''
    if (next?.diagnosis && !next.diagnosis.counterfactual) {
      verifying.value = true
      try {
        const counter = await postData(`/questions/${questionId}/diagnosis/counterfactual`, {})
        if (active && current === revision) item.value.diagnosis.counterfactual = counter
      } catch {
        // A missing older repair does not prevent reading the actual diagnosis.
      } finally {
        if (active && current === revision) verifying.value = false
      }
    }
  } catch {
    if (active && current === revision) error.value = true
  }
}

/* =========================================================
   生成诊断
========================================================= */

async function generate() {
  if (busy.value || !active || !item.value?.confirmed) return
  busy.value = true
  generating.value = true
  generationError.value = ''
  const questionId = id.value
  const operation = hasStudentWork.value ? 'diagnose' : 'analyze'
  try {
    // The diagnosis endpoint creates a missing analysis itself. One request
    // also keeps an existing reference explanation intact.
    await postData(`/questions/${questionId}/${operation}`, {}, { silent: true, timeout: 180000 })
    if (active && id.value === questionId) await load(false)
  } catch (err) {
    if (active && id.value === questionId)
      generationError.value = err.message || '分析未完成，请重试。'
  } finally {
    generating.value = false
    busy.value = false
  }
}

/* =========================================================
   进入教学
========================================================= */

async function startLearning() {
  if (busy.value || !active || !item.value) return
  busy.value = true
  entryError.value = ''
  const current = revision,
    questionId = id.value
  try {
    const task = await requestLearningTask(questionId)
    if (active && current === revision) go(`/pages/task/task?id=${task.id}`)
  } catch (err) {
    if (active && current === revision)
      entryError.value = err.message || '暂时无法开始学习，请重试。'
  } finally {
    busy.value = false
  }
}
function continueFromSummary() {
  if (diagnosisState.value.kind === 'clear') return startLearning()
  return openKnowledgeGraph()
}

function openKnowledgeGraph() {
  go(`/pages/knowledge/knowledge?id=${id.value}`)
}

/* =========================================================
   开始人工修正
========================================================= */

function beginEdit() {
  correctionError.value = ''
  Object.assign(correction, {
    first_error_step: Number.isInteger(diagnosis.value?.first_error_step)
      ? diagnosis.value.first_error_step + 1
      : '',

    error_type: diagnosis.value?.error_type || 'unknown',

    root_misconception: diagnosis.value?.root_misconception || '',

    error_location: diagnosis.value?.error_location || '',

    recommended_strategy: diagnosis.value?.recommended_strategy || '',
  })

  editing.value = true
}

/* =========================================================
   保存人工修正
========================================================= */

async function saveCorrection() {
  if (busy.value) return
  correctionError.value = ''
  const clear = ['exact', 'equivalent'].includes(correction.error_type)
  const number = correction.first_error_step
  const first = clear || number === '' || number == null ? null : Number(number) - 1
  if (
    first !== null &&
    (!Number.isInteger(first) || first < 0 || first >= (item.value?.student_steps?.length || 0))
  ) {
    correctionError.value = '请填写实际作答中的步骤编号，从第1步开始；尚未定位可留空。'
    return
  }
  busy.value = true

  try {
    await patchData(`/questions/${id.value}/diagnosis`, {
      ...correction,
      first_error_step: first,
    })

    editing.value = false

    await load()

    uni.showToast({
      title: '诊断修正已保存',
      icon: 'success',
    })
  } catch (err) {
    correctionError.value = err.message || '修正未保存，请保留当前内容后重试。'
  } finally {
    busy.value = false
  }
}

/* =========================================================
   页面加载
========================================================= */

onLoad((q) => {
  id.value = q.id || ''
})
onShow(() => {
  active = true
  load()
})
function leave() {
  active = false
  revision++
  item.value = null
  verifying.value = false
}
onHide(leave)
onUnload(leave)
</script>

<style scoped lang="scss">
.status-message {
  display: block;
  margin-top: 12px;
  font-size: 15px;
  line-height: 1.6;
  color: var(--color-text-secondary);
}
.diagnosis-page {
  min-height: 100vh;
  background: var(--color-bg);
  color: var(--color-text-primary);
}
.page-content {
  box-sizing: border-box;
  padding: 24px var(--space-page) 50px;
}
.summary-card {
  padding: 4px 0 14px;
  border-bottom: 0.5px solid var(--color-border);
}
.summary-kicker {
  display: block;
  color: var(--color-text-secondary);
  font-size: 12px;
}
.summary-title {
  display: block;
  margin-top: 6px;
  color: var(--color-text-primary);
  font-size: 18px;
  font-weight: 600;
  line-height: 1.5;
}
.answer-summary-card {
  display: grid;
  grid-template-columns: 1fr 1fr;
  padding: 2px 0 13px;
  border-bottom: 0.5px solid var(--color-border);
}
.answer-row {
  padding: 5px 10px 5px 0;
}
.correct-answer-row {
  padding-left: 12px;
  border-left: 0.5px solid var(--color-border);
}
.answer-label,
.answer-value {
  display: block;
}
.answer-label {
  color: var(--color-text-secondary);
  font-size: 12px;
}
.answer-value {
  margin-top: 5px;
  font-size: 18px;
  font-weight: 600;
}
.correct-answer {
  color: var(--color-primary);
}
.section-title {
  margin: 15px 0 7px;
  color: var(--color-text-primary);
  font-size: 14px;
  font-weight: 600;
  line-height: 1.4;
}
.reason-card {
  padding: 0 0 6px;
}
.analysis-lead {
  display: block;
  margin: 7px 0 5px;
  color: var(--color-text-secondary);
  font-size: 12px;
}
.reason-text {
  display: block;
  margin: 5px 0;
  color: var(--color-text-primary);
  font-size: 14px;
  line-height: 1.85;
}
.option-quote {
  display: block;
  padding: 9px 10px;
  border-radius: 8px;
  background: var(--color-surface);
  font-size: 14px;
  line-height: 1.75;
}
.thought-card {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 11px 10px;
  border: 0;
  border-radius: 8px;
  background: #fff;
}
.thought-mark {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
  min-height: 21px;
}
.thought-text {
  flex: 1;
  min-width: 0;
  color: var(--color-text-primary);
  font-size: 14px;
  line-height: 1.75;
}
.student-thought {
  background: var(--color-error-soft);
}
.correct-thought {
  background: var(--color-primary-soft);
}
.tutor-btn {
  margin-top: 14px;
}
.more-label {
  display: block;
  margin: 18px 0 7px;
  color: var(--color-text-secondary);
  font-size: 12px;
}
.secondary-area {
  border-top: 0.5px solid var(--color-border);
}
.secondary-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-height: 46px;
  border-bottom: 0.5px solid var(--color-border);
}
.secondary-title {
  font-size: 14px;
}
.path-section,
.detail-panel {
  padding: 10px 0;
  border-bottom: 0.5px solid var(--color-border);
}
.segmented {
  display: flex;
  gap: 14px;
  border-bottom: 0.5px solid var(--color-border);
}
.segmented > view {
  padding: 7px 2px 8px;
  color: var(--color-text-secondary);
  font-size: 13px;
}
.segmented .active {
  border-bottom: 1.5px solid var(--color-primary);
  color: var(--color-primary);
  font-weight: 500;
}
.step-row {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  padding: 12px 0;
  border-bottom: 0.5px solid var(--color-border);
}
.step-row:last-child {
  border: 0;
}
.step-number {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
  width: 18px;
  height: 22px;
  color: var(--color-text-tertiary);
  font-size: 12px;
}
.step-main {
  flex: 1;
  min-width: 0;
}
.step-head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 4px 8px;
}
.step-content {
  flex: 1;
  min-width: 0;
  color: var(--color-text-primary);
  font-size: 14px;
  line-height: 1.75;
}
.step-row.first .step-number {
  color: var(--color-error);
}
.first-tag {
  color: var(--color-error);
  font-size: 12px;
}
.step-caption,
.propagated-text {
  display: block;
  margin-top: 4px;
  color: var(--color-text-secondary);
  font-size: 12px;
  line-height: 1.65;
}
.empty-path {
  padding: 14px 0;
  color: var(--color-text-secondary);
  font-size: 13px;
}
.detail-item {
  display: grid;
  grid-template-columns: 60px 1fr;
  gap: 9px;
  padding: 6px 0;
}
.detail-label {
  color: var(--color-text-secondary);
  font-size: 12px;
  line-height: 1.75;
}
.detail-value {
  min-width: 0;
  color: var(--color-text-primary);
  font-size: 13px;
  line-height: 1.75;
}
.correction-card {
  margin-top: 15px;
  padding: 12px 0;
  border-top: 0.5px solid var(--color-border);
}
.correction-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}
.correction-title {
  font-size: 14.5px;
  font-weight: 600;
}
.correction-cancel {
  padding: 6px 0;
  color: var(--color-text-secondary);
  font-size: 13px;
}
.two-column {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.field {
  margin-top: 10px;
}
.field-label {
  display: block;
  margin-bottom: 5px;
  color: var(--color-text-secondary);
  font-size: 12px;
}
.field-input,
.field-picker,
.field-textarea {
  box-sizing: border-box;
  width: 100%;
  min-height: 41px;
  padding: 9px 10px;
  border: 0.5px solid var(--color-border);
  border-radius: 4px;
  background: #fff;
  color: var(--color-text-primary);
  font-size: 13px;
  line-height: 1.6;
}
.field-textarea {
  min-height: 75px;
}
.feedback-link {
  display: block;
  padding: 13px 0;
  color: var(--color-text-secondary);
  font-size: 12px;
}
.solution-intro {
  padding: 4px 0 13px;
  border-bottom: 0.5px solid var(--color-border);
}
.solution-kicker,
.solution-title,
.solution-desc {
  display: block;
}
.solution-kicker {
  font-size: 12px;
  color: var(--color-text-secondary);
}
.solution-title {
  margin-top: 6px;
  font-size: 17px;
  font-weight: 600;
  line-height: 1.5;
}
.solution-desc {
  margin-top: 6px;
  color: var(--color-text-secondary);
  font-size: 13px;
  line-height: 1.7;
}
.solution-card {
  border-top: 0.5px solid var(--color-border);
}
.solution-step {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 12px 0;
  border-bottom: 0.5px solid var(--color-border);
}
.solution-step > text {
  flex: none;
  width: 18px;
  color: var(--color-text-tertiary);
  font-size: 12px;
  line-height: 1.75;
}
.solution-step :deep(.math-text) {
  flex: 1;
  min-width: 0;
  font-size: 14px;
  line-height: 1.75;
}
.answer-card {
  margin-top: 12px;
  padding: 11px 0;
  border-bottom: 0.5px solid var(--color-border);
}
.answer-card > text {
  color: var(--color-text-secondary);
  font-size: 12px;
}
.answer-card :deep(.math-text) {
  display: block;
  margin-top: 6px;
  font-size: 14.5px;
  font-weight: 600;
}
.empty-card {
  padding: 20px 0;
}
.empty-title,
.empty-desc {
  display: block;
}
.empty-title {
  font-size: 16px;
  font-weight: 600;
}
.empty-desc {
  margin-top: 7px;
  color: var(--color-text-secondary);
  font-size: 13px;
  line-height: 1.7;
}
</style>
