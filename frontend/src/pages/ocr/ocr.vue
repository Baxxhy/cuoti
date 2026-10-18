<template>
  <view class="page confirm-page">
    <app-header title="确认题目" back :back-fallback="`/pages/crop/crop?id=${id}`" />

    <view v-if="processing" class="page-content">
      <state-panel state="loading" />
      <text class="notice">{{ processingStatus }}</text>
    </view>
    <state-panel
      v-else-if="error"
      state="error"
      :message="errorMessage"
      :retry-text="jobCancelled ? '返回错题本' : '重新加载'"
      @retry="jobCancelled ? uni.redirectTo({ url: '/pages/problem/list' }) : load()"
    />
    <state-panel v-else-if="!item" state="loading" />
    <template v-else>
      <view v-if="item.assets?.length" class="question-image">
        <image
          v-if="cropAsset && !imageError"
          :src="cropAsset.url"
          mode="widthFix"
          @error="imageError = true"
        />
        <view v-else class="image-unavailable">
          <text>题目图片暂时无法显示</text>
        </view>
      </view>

      <view class="page-content confirm-content">
        <view class="meta-row">
          <template v-if="editing">
            <picker :range="subjects" @change="form.subject = subjects[$event.detail.value]">
              <view class="meta-picker">
                {{ form.subject || '待确认' }}
                <view class="picker-chevron" />
              </view>
            </picker>
            <picker :range="grades" @change="form.grade = grades[$event.detail.value]">
              <view class="meta-picker">
                {{ form.grade || '待确认年级' }}
                <view class="picker-chevron" />
              </view>
            </picker>
            <picker :range="questionTypeLabels" @change="setQuestionType">
              <view class="meta-picker">
                {{ questionTypeLabel(form.question_type) }}
                <view class="picker-chevron" />
              </view>
            </picker>
          </template>
          <template v-else>
            <text class="meta-chip">{{ form.subject || '待确认学科' }}</text>
            <text class="meta-chip">{{ form.grade || '待确认年级' }}</text>
            <text class="meta-chip">{{ questionTypeLabel(form.question_type) }}</text>
          </template>
        </view>

        <view class="content-section question-section">
          <text class="section-label">题干</text>
          <textarea
            v-if="editing"
            v-model="form.question_text"
            class="content-editor question-editor"
            auto-height
          />
          <math-text v-else class="question-text" :text="form.question_text" />
          <view v-if="questionFigures.length" class="question-figures">
            <image
              v-for="figure in questionFigures"
              :key="figure.id"
              :src="figure.url"
              mode="widthFix"
              :aria-label="figure.description || '题目配图'"
            />
          </view>
        </view>

        <view v-if="form.options.length" class="content-section">
          <text class="section-label">选项</text>
          <view v-if="editing" class="option-edit-list">
            <view
              v-for="(option, index) in form.options"
              :key="option.label || index"
              class="option-edit"
            >
              <text>{{ optionLabel(option, index) }}</text>
              <input v-model="option.text" />
            </view>
          </view>
          <view v-else class="option-list">
            <view
              v-for="(option, index) in form.options"
              :key="option.label || index"
              class="option-row"
            >
              <text class="option-label">{{ optionLabel(option, index) }}</text>
              <math-text :text="optionValue(option)" />
            </view>
          </view>
        </view>

        <view v-if="hasAnswer || editing" class="content-section">
          <text class="section-label">你的答案</text>
          <textarea
            v-if="editing"
            v-model="form.student_answer"
            class="content-editor"
            auto-height
          />
          <math-text v-else class="answer-text" :text="form.student_answer" />
        </view>

        <view class="content-section working-section">
          <view class="section-heading">
            <text class="section-label">你的解题过程</text>
            <text v-if="hasWorking && !editing" class="section-action" @click="editing = true">
              修改
            </text>
          </view>
          <view v-if="displayedSteps.length" class="step-list">
            <view v-for="(step, index) in displayedSteps" :key="step.id || index" class="step-row">
              <text class="step-index">{{ index + 1 }}</text>
              <textarea
                v-if="editing || draftStepIndex === index"
                v-model="step.text"
                class="step-editor"
                @input="step.formula = ''"
                auto-height
              />
              <math-text v-else class="step-text" :text="step.formula || step.text" />
              <text
                v-if="editing || draftStepIndex === index"
                class="remove-step"
                @click="removeStep(index)"
              >
                删除
              </text>
            </view>
          </view>
          <view v-else class="working-empty">
            <text>暂未发现解题过程</text>
            <text>可以使用文字补充</text>
          </view>
          <view class="working-actions">
            <button class="working-action" @click="addTextStep">
              <uni-icons type="compose" size="22" color="var(--color-primary)" />
              <text>添加文字</text>
            </button>
          </view>
        </view>

        <view v-if="visibleMarks.length" class="content-section">
          <text class="section-label">教师批注</text>
          <view v-for="(mark, index) in visibleMarks" :key="mark.id || index" class="teacher-mark">
            <text class="mark-type">{{ markTypeLabel(mark.mark_type) }}</text>
            <input v-if="editing" v-model="mark.comment" />
            <math-text v-else :text="mark.comment" />
          </view>
        </view>

        <view v-if="!hasAnswer && !hasWorking" class="absence-note">
          <text>暂未发现你的作答</text>
        </view>

        <text v-if="notice" class="notice">{{ notice }}</text>
      </view>

      <view class="confirm-actions">
        <view class="confirm-actions-inner">
          <text class="edit-action" @click="toggleEditing">
            {{ editing ? '预览修改' : '内容有误？修改' }}
          </text>
          <button
            class="primary-btn"
            :disabled="busy || !form.question_text.trim()"
            @click="editOnly ? saveChanges() : confirm()"
          >
            {{
              busy ? (editOnly ? '正在保存…' : '正在分析…') : editOnly ? '保存修改' : '确认并分析'
            }}
          </button>
        </view>
      </view>
    </template>
  </view>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { onLoad, onUnload } from '@dcloudio/uni-app'
import { getData, postData } from '@/api/index.js'
import { editedStudentSteps } from '@/utils/question.js'
import { waitForProcessingJob } from '@/utils/processing.js'
import { CORE_SUBJECTS as subjects, MIDDLE_SCHOOL_GRADES as grades } from '@/constants/education.js'

const questionTypeCodes = [
  'fill_blank',
  'choice',
  'multiple_choice',
  'calculation',
  'proof',
  'subjective',
  'comprehensive',
  'other',
]
const questionTypeMap = {
  fill_blank: '填空题',
  choice: '单选题',
  multiple_choice: '多选题',
  calculation: '计算题',
  proof: '证明题',
  subjective: '主观题',
  comprehensive: '综合题',
  other: '其他题型',
}
const questionTypeLabels = questionTypeCodes.map((code) => questionTypeMap[code])
const markTypeMap = {
  check: '对勾',
  cross: '叉号',
  correction: '订正',
  comment: '文字批注',
  other: '其他',
}

const id = ref('')
const item = ref(null)
const error = ref(false)
const busy = ref(false)
const editOnly = ref(false)
const editing = ref(false)
const draftStepIndex = ref(null)
const notice = ref('')
const imageError = ref(false)
const processing = ref(false)
const processingStatus = ref('正在重新识别，请稍候…')
const errorMessage = ref('')
const jobId = ref('')
const jobCancelled = ref(false)
let active = true
let jobFailed = false
let loading = false
const form = reactive({
  question_text: '',
  student_answer: '',
  subject: '',
  grade: '',
  question_type: 'other',
  formulas: [],
  options: [],
  knowledge_points: [],
  student_steps: [],
  teacher_marks: [],
})

const cropAsset = computed(() => item.value?.assets?.find((asset) => asset.kind === 'crop') || null)
const questionFigures = computed(() => item.value?.question_figures || [])
const visibleSteps = computed(() =>
  form.student_steps.filter((step) => String(step.text || step.formula || '').trim()),
)
const displayedSteps = computed(() =>
  editing.value || draftStepIndex.value !== null ? form.student_steps : visibleSteps.value,
)
const visibleMarks = computed(() =>
  form.teacher_marks.filter((mark) => String(mark.comment || '').trim()),
)
const hasAnswer = computed(() => Boolean(String(form.student_answer || '').trim()))
const hasWorking = computed(() => visibleSteps.value.length > 0)

function normalizeOption(option, index) {
  if (typeof option === 'string') return { label: String.fromCharCode(65 + index), text: option }
  return {
    ...option,
    label: option.label || String.fromCharCode(65 + index),
    text: option.text || '',
  }
}

function hydrate(data) {
  item.value = data
  imageError.value = false
  Object.assign(form, {
    question_text: data.question_text || '',
    student_answer: data.student_answer || '',
    subject: data.subject || '',
    grade: data.grade || '',
    question_type: questionTypeCodes.includes(data.question_type)
      ? data.question_type
      : {
          单选题: 'choice',
          选择题: 'choice',
          多选题: 'multiple_choice',
          填空题: 'fill_blank',
          计算题: 'calculation',
          证明题: 'proof',
          综合题: 'comprehensive',
        }[data.question_type] || 'other',
    formulas: [...(data.formulas || [])],
    options: (data.options || []).map(normalizeOption),
    knowledge_points: [...(data.knowledge_points || data.analysis?.knowledge_points || [])],
    student_steps: (data.student_steps || []).map((step) => ({
      ...step,
      text: step.text || step.formula || step.expression || '',
    })),
    teacher_marks: (data.teacher_marks || []).map((mark) => ({ ...mark })),
  })
}

async function load() {
  if (loading) return
  loading = true
  error.value = false
  try {
    const current = await getData(`/questions/${id.value}`)
    if (!active) return
    if (current.status === 'archived') {
      throw Object.assign(new Error('题目已归档，请返回错题本'), { jobCancelled: true })
    }
    if (current.processing_job) {
      jobId.value = current.processing_job.id
    } else if (['needs_confirmation', 'ocr_draft'].includes(current.status)) {
      jobId.value = ''
      jobFailed = false
    }
    if (jobFailed) {
      const previousJobId = jobId.value
      try {
        const result = await postData(
          previousJobId ? `/jobs/${previousJobId}/retry` : `/questions/${id.value}/reprocess`,
          {},
        )
        jobId.value = result.job_id || result.id || previousJobId
      } catch (err) {
        // A lost retry response may leave the original task running or completed.
        if (!previousJobId || err.statusCode !== 409) throw err
      }
      if (!jobId.value) throw new Error('未收到识别任务，请稍后重试。')
      jobFailed = false
    }
    if (jobId.value) {
      processing.value = true
      const completed = await waitForProcessingJob(jobId.value, {
        getJob: (value) => getData(`/jobs/${value}`),
        isActive: () => active,
        onProgress: (job) => {
          processingStatus.value = `正在识别题目… ${job.progress || 0}%`
        },
      })
      if (!completed) return
      jobId.value = ''
    }
    const data = await getData(`/questions/${id.value}`)
    if (active && data.status === 'awaiting_crop') {
      uni.redirectTo({ url: `/pages/crop/crop?id=${id.value}` })
    } else if (active) hydrate(data)
  } catch (err) {
    if (err.jobFailed) jobFailed = true
    if (err.jobCancelled) jobCancelled.value = true
    errorMessage.value = err.message || '暂时无法加载，请重试'
    error.value = true
  } finally {
    processing.value = false
    loading = false
  }
}

function questionTypeLabel(code) {
  return questionTypeMap[code] || '其他题型'
}

function setQuestionType(event) {
  form.question_type = questionTypeCodes[event.detail.value] || 'other'
}

function optionLabel(option, index) {
  return option.label || String.fromCharCode(65 + index)
}

function optionValue(option) {
  return typeof option === 'string' ? option : option.text
}

function markTypeLabel(type) {
  return markTypeMap[type] || '批注'
}

function toggleEditing() {
  discardEmptySteps()
  draftStepIndex.value = null
  editing.value = !editing.value
  notice.value = editing.value ? '可直接修改识别有误的内容' : ''
}

function newStep(text = '') {
  return { text, raw_text: text, formula: '', bbox: [], confidence: 1, source: 'user' }
}

function discardEmptySteps() {
  for (let index = form.student_steps.length - 1; index >= 0; index -= 1) {
    const step = form.student_steps[index]
    if (!String(step.text || '').trim() && !String(step.formula || '').trim())
      form.student_steps.splice(index, 1)
  }
}

function addTextStep() {
  const emptyIndex = form.student_steps.findIndex(
    (step) => !String(step.text || '').trim() && !String(step.formula || '').trim(),
  )
  if (emptyIndex >= 0) {
    notice.value = `第 ${emptyIndex + 1} 步还没有内容，请先填写或删除`
    return
  }
  form.student_steps.push(newStep())
  draftStepIndex.value = form.student_steps.length - 1
}

function removeStep(index) {
  form.student_steps.splice(index, 1)
  draftStepIndex.value = null
}

function payload() {
  return JSON.parse(
    JSON.stringify({ ...form, student_steps: editedStudentSteps(form.student_steps) }),
  )
}

async function saveChanges() {
  if (busy.value || !form.question_text.trim()) return
  discardEmptySteps()
  busy.value = true
  notice.value = ''
  try {
    await postData(`/questions/${id.value}/confirm`, payload())
    if (active) uni.redirectTo({ url: `/pages/detail/detail?id=${id.value}` })
  } catch (err) {
    notice.value = err.message || '修改未保存，请重试。已填写的内容仍保留。'
  } finally {
    busy.value = false
  }
}

async function confirm() {
  if (busy.value || !form.question_text.trim()) return
  discardEmptySteps()
  busy.value = true
  notice.value = ''
  try {
    await postData(`/questions/${id.value}/confirm`, payload())
    await postData(`/questions/${id.value}/analyze`, {})
    await postData(`/questions/${id.value}/diagnose`, {})
    if (active) uni.redirectTo({ url: `/pages/diagnosis/diagnosis?id=${id.value}` })
  } catch (err) {
    notice.value = err.message || '分析未完成，请重试。已填写的内容仍保留。'
  } finally {
    busy.value = false
  }
}

onLoad((query) => {
  id.value = query.id || ''
  jobId.value = query.job || ''
  editOnly.value = query.edit === '1'
  editing.value = editOnly.value
  load()
})
onUnload(() => {
  active = false
})
</script>

<style scoped lang="scss">
.confirm-page {
  padding-bottom: 95px;
}
.question-image {
  width: 100%;
  padding: 12px 16px 0;
  background: var(--color-bg);
}
.question-image image {
  display: block;
  width: 100%;
  border: 0.5px solid var(--color-border);
  border-radius: 4px;
  background: #fff;
  image-orientation: from-image;
}
.image-unavailable {
  min-height: 130px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 0.5px solid var(--color-border);
  border-radius: 4px;
  background: #fff;
  color: var(--color-text-secondary);
  font-size: 13px;
}
.confirm-content {
  padding-top: 11px;
}
.meta-row {
  display: flex;
  gap: 6px;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 9px;
}
.meta-picker {
  min-height: 28px;
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 4px 9px;
  border: 0.5px solid var(--color-border);
  border-radius: 4px;
  background: #fff;
  color: #475467;
  font-size: 12px;
}
.meta-chip {
  color: var(--color-text-secondary);
  font-size: 12px;
  padding-right: 7px;
  border-right: 0.5px solid var(--color-border);
}
.meta-chip:last-child {
  border: 0;
}
.picker-chevron {
  width: 5px;
  height: 5px;
  border-right: 1px solid var(--color-text-tertiary);
  border-bottom: 1px solid var(--color-text-tertiary);
  transform: rotate(45deg);
  margin-top: -5rpx;
}
.content-section {
  padding: 14px 0;
  border-bottom: 0.5px solid var(--color-border-subtle, #eaecf0);
}
.question-section {
  padding-top: 6px;
}
.question-figures {
  display: flex;
  flex-direction: column;
  gap: 7px;
  margin-top: 11px;
}
.question-figures image {
  display: block;
  width: 100%;
  border: 0.5px solid var(--color-border);
  border-radius: 4px;
  background: #fff;
}
.section-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 7px;
}
.section-heading .section-label {
  margin: 0;
}
.section-label {
  display: block;
  margin-bottom: 7px;
  color: var(--color-text-secondary);
  font-size: 12px;
  font-weight: 600;
}
.section-action {
  min-width: 32px;
  text-align: right;
  color: var(--color-primary-hover);
  font-size: 12px;
}
.question-text {
  display: block;
  color: var(--color-text-primary);
  font-size: 15.5px;
  font-weight: 500;
  line-height: 1.8;
  white-space: pre-wrap;
}
.answer-text,
.step-text {
  color: var(--color-text-primary);
  font-size: 14px;
  line-height: 1.7;
  white-space: pre-wrap;
}
.content-editor,
.step-editor {
  width: 100%;
  min-height: 56px;
  padding: 10px 11px;
  border: 0.5px solid var(--color-border);
  border-radius: 4px;
  background: #fff;
  color: var(--color-text-primary);
  font-size: 14px;
  line-height: 1.65;
}
.question-editor {
  min-height: 90px;
}
.option-list,
.option-edit-list,
.step-list {
  display: flex;
  flex-direction: column;
  gap: 7px;
}
.option-row,
.option-edit,
.step-row,
.teacher-mark {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}
.option-label,
.step-index {
  flex: none;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: transparent;
  color: var(--color-text-secondary);
  font-size: 12px;
  font-weight: 600;
}
.option-row :deep(.math-text),
.teacher-mark :deep(.math-text) {
  flex: 1;
  min-width: 0;
  padding-top: 2px;
  color: var(--color-text-primary);
  font-size: 14px;
}
.option-edit input,
.teacher-mark input {
  flex: 1;
  min-height: 34px;
  padding: 5px 8px;
  border: 0.5px solid var(--color-border);
  border-radius: 4px;
  background: #fff;
  font-size: 14px;
}
.step-editor,
.step-text {
  flex: 1;
  min-width: 0;
}
.remove-step {
  flex: none;
  padding: 5px 0;
  color: var(--color-error);
  font-size: 12px;
}
.working-empty text {
  display: block;
  color: var(--color-text-secondary);
  font-size: 13px;
}
.working-empty text + text {
  margin-top: 2px;
  color: var(--color-text-tertiary);
  font-size: 12px;
}
.working-actions {
  display: grid;
  grid-template-columns: 1fr;
  gap: 6px;
  margin-top: 9px;
}
.working-action {
  height: 39px;
  min-height: 39px;
  margin: 0;
  padding: 0 9px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  box-sizing: border-box;
  border: 0;
  border-radius: 4px;
  border: 0.5px solid var(--color-border);
  background: #fff;
  color: var(--color-primary);
  font-size: 12px;
  font-weight: 600;
}
.working-action::after {
  border: 0;
}
.working-action[disabled] {
  color: var(--color-text-tertiary);
  background: #f2f4f7;
}
.mark-type {
  flex: none;
  padding: 2.5px 6px;
  border-radius: 5px;
  background: var(--color-surface-subtle);
  color: var(--color-text-secondary);
  font-size: 12px;
}
.teacher-mark + .teacher-mark {
  margin-top: 7px;
}
.absence-note {
  margin-top: 12px;
  padding: 11px 12px;
  border: 0.5px solid var(--color-border);
  border-radius: 4px;
  background: #fff;
  color: var(--color-text-secondary);
  font-size: 13px;
}
.notice {
  display: block;
  margin-top: 10px;
  text-align: center;
  color: var(--color-primary-hover);
  font-size: 12px;
}
.confirm-actions {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 80;
  display: flex;
  align-items: center;
  gap: 13px;
  padding: 9px 16px calc(9px + env(safe-area-inset-bottom));
  border-top: 0.5px solid var(--color-border);
  background: rgba(255, 255, 255, 0.98);
}
.edit-action {
  flex: none;
  min-height: 40px;
  display: flex;
  align-items: center;
  color: var(--color-primary-hover);
  font-size: 13px;
}
.confirm-actions .primary-btn {
  flex: 1;
  margin: 0;
}
.confirm-actions-inner {
  display: flex;
  align-items: center;
  gap: 13px;
  width: 100%;
  max-width: 756px;
  margin: 0 auto;
}
@media (min-width: 768px) {
  .confirm-actions {
    width: 100%;
    max-width: 960px;
    box-sizing: border-box;
    margin: 0 auto;
    padding-left: 32px;
    padding-right: 32px;
  }
  .question-image {
    max-width: 820px;
    margin: 0 auto;
  }
}
</style>
