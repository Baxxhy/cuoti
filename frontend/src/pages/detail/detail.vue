<template>
  <view class="page detail-page">
    <app-header
      title="错题详情"
      back
      :back-fallback="
        reviewReturnId
          ? `/pages/review/review?plan=${encodeURIComponent(reviewReturnId)}&question=${encodeURIComponent(id)}`
          : undefined
      "
    >
      <button
        class="icon-action"
        role="button"
        tabindex="0"
        aria-label="更多操作"
        @click="showActions"
        @keydown.enter.prevent="showActions"
        @keydown.space.prevent
        @keyup.space.prevent="showActions"
      >
        <uni-icons
          aria-hidden="true"
          type="more-filled"
          size="23"
          color="var(--color-text-secondary)"
        />
      </button>
    </app-header>
    <state-panel
      v-if="!item"
      :state="!id || error ? 'error' : 'loading'"
      :message="!id ? '请先选择一道错题' : undefined"
      :retry-text="!id ? '选择错题' : '重新加载'"
      @retry="id ? load() : go('/pages/problem/list')"
    />
    <view v-else class="page-content">
      <view class="detail-sections" aria-label="本题内容分区">
        <button
          tabindex="0"
          role="button"
          v-for="tab in detailSections"
          :key="tab.key"
          :aria-pressed="section === tab.key"
          :class="{ active: section === tab.key }"
          @click="section = tab.key"
          @keydown.enter.prevent="section = tab.key"
          @keydown.space.prevent
          @keyup.space.prevent="section = tab.key"
        >
          {{ tab.label }}
        </button>
      </view>
      <view v-if="section === 'question'" class="question-section">
        <button
          tabindex="0"
          role="button"
          v-if="mainImage"
          class="quiet-action"
          @click="preview(mainImage.url)"
          @keydown.enter.prevent="preview(mainImage.url)"
          @keydown.space.prevent
          @keyup.space.prevent="preview(mainImage.url)"
        >
          查看原图
        </button>
        <math-text
          class="question-text"
          :text="item.question_text || '题干等待核对'"
          :subject="item.subject"
        />
        <view v-if="item.options?.length" class="question-options">
          <math-text
            v-for="(option, index) in item.options"
            :key="index"
            :text="optionText(option, index)"
            :subject="item.subject"
          />
        </view>
        <image
          v-for="figure in item.question_figures || []"
          :key="figure.id || figure.url"
          class="detail-figure"
          :src="figure.url"
          mode="widthFix"
          :aria-label="figure.description || '题目配图'"
          @click="preview(figure.url)"
        />
        <view class="answer-grid">
          <view>
            <text>我当时的答案</text>
            <math-text class="student-answer" :text="item.student_answer || '未填写'" />
          </view>
          <view v-if="showAnswer && item.analysis?.final_answer">
            <text>正确答案</text>
            <math-text :text="item.analysis.final_answer" />
          </view>
        </view>
      </view>

      <view v-if="section === 'question' && item.reference_steps?.length" class="secondary-content">
        <view class="fold-row" @click="toggle('reference')">
          <text>参考步骤</text>
          <uni-icons
            aria-hidden="true"
            :type="opened === 'reference' ? 'top' : 'bottom'"
            size="18"
            color="var(--color-text-tertiary)"
          />
        </view>
        <view v-if="opened === 'reference'" class="fold-body">
          <view
            v-for="(step, index) in item.reference_steps"
            :key="step.id || index"
            class="step-row"
          >
            <i>{{ index + 1 }}</i>
            <math-text :text="step.text" />
          </view>
        </view>
      </view>
      <view v-if="section === 'question'" class="detail-tools">
        <button
          tabindex="0"
          role="button"
          v-if="item.analysis?.final_answer"
          class="quiet-action"
          :aria-expanded="showAnswer"
          @click="showAnswer = !showAnswer"
          @keydown.enter.prevent="showAnswer = !showAnswer"
          @keydown.space.prevent
          @keyup.space.prevent="showAnswer = !showAnswer"
        >
          {{ showAnswer ? '收起参考答案' : '查看参考答案' }}
        </button>
        <button
          :aria-disabled="busy"
          :tabindex="busy ? -1 : 0"
          role="button"
          class="quiet-action"
          :disabled="busy"
          :aria-pressed="!!item.favorite"
          @click="toggleFavorite"
          @keydown.enter.prevent="!busy && toggleFavorite"
          @keydown.space.prevent
          @keyup.space.prevent="!busy && toggleFavorite"
        >
          {{ item.favorite ? '取消收藏' : '收藏题目' }}
        </button>
      </view>
      <view v-if="section !== 'records' && item.diagnosis" class="issue-section">
        <text class="section-kicker">
          {{ diagnosisState.kind === 'finding' ? '错因' : diagnosisState.title }}
        </text>
        <math-text v-if="firstErrorTitle" class="issue-title" :text="firstErrorTitle" inline />
        <math-text
          v-if="diagnosisState.kind === 'finding' && item.diagnosis.first_error_text"
          class="issue-formula"
          :text="item.diagnosis.first_error_text"
        />
        <math-text
          class="issue-reason"
          :text="
            diagnosisState.kind === 'finding'
              ? item.diagnosis.root_misconception
              : diagnosisState.message
          "
          inline
        />
        <text class="text-action" @click="go(`/pages/diagnosis/diagnosis?id=${id}`)">
          查看错因
          <uni-icons aria-hidden="true" type="right" size="16" color="var(--color-primary)" />
        </text>
      </view>

      <text v-if="!item.confirmed || !item.diagnosis" class="detail-status">
        {{
          !item.confirmed
            ? '先核对题目与当时的作答'
            : item.diagnosis
              ? diagnosisState.kind === 'finding'
                ? '可以开始订正'
                : '可以开始练习'
              : '先找出这道题的错因'
        }}
      </text>
      <button
        v-if="section !== 'records'"
        :aria-disabled="busy"
        :tabindex="busy ? -1 : 0"
        role="button"
        class="primary-btn"
        :disabled="busy"
        @click="continueLearning"
        @keydown.enter.prevent="!busy && continueLearning"
        @keydown.space.prevent
        @keyup.space.prevent="!busy && continueLearning"
      >
        {{
          busy
            ? '正在打开…'
            : !item.confirmed
              ? '核对题目'
              : !item.analysis || !item.diagnosis
                ? '分析错因'
                : '订正这道题'
        }}
      </button>
      <button
        tabindex="0"
        role="button"
        v-if="!item.assets?.length && !item.analysis"
        class="quiet-action"
        @click="go(`/pages/ocr/ocr?id=${id}&edit=1`)"
        @keydown.enter.prevent="go(`/pages/ocr/ocr?id=${id}&edit=1`)"
        @keydown.space.prevent
        @keyup.space.prevent="go(`/pages/ocr/ocr?id=${id}&edit=1`)"
      >
        修改录入内容
      </button>
      <text v-if="entryError" class="account-notice" role="alert">{{ entryError }}</text>
      <view v-if="section === 'learn' && item.diagnosis" class="detail-evidence-entries">
        <button
          aria-label="错因回放"
          role="button"
          tabindex="0"
          class="disclosure-link"
          @keydown.enter.prevent="go(`/pages/replay/replay?id=${id}`)"
          @keydown.space.prevent
          @keyup.space.prevent="go(`/pages/replay/replay?id=${id}`)"
          @click="go(`/pages/replay/replay?id=${id}`)"
        >
          错因回放
          <uni-icons aria-hidden="true" type="right" size="18" />
        </button>
        <button
          aria-label="学习安排"
          role="button"
          tabindex="0"
          class="disclosure-link"
          @keydown.enter.prevent="go(`/pages/repair/repair?id=${id}`)"
          @keydown.space.prevent
          @keyup.space.prevent="go(`/pages/repair/repair?id=${id}`)"
          @click="go(`/pages/repair/repair?id=${id}`)"
        >
          学习安排
          <uni-icons aria-hidden="true" type="right" size="18" />
        </button>
      </view>
      <view
        v-if="section === 'learn'"
        class="learning-tools"
        :class="{ 'without-practice': !item.diagnosis }"
      >
        <button
          class="tool-row"
          role="button"
          tabindex="0"
          :disabled="busy"
          @click="continueLegacyLearning"
          @keydown.enter.prevent="!busy && continueLegacyLearning()"
          @keydown.space.prevent
          @keyup.space.prevent="!busy && continueLegacyLearning()"
        >
          <view class="tool-icon" aria-hidden="true">
            <uni-icons aria-hidden="true" type="chat" size="25" color="var(--color-primary)" />
          </view>
          <text class="tool-label">AI 讲解</text>
        </button>
        <button
          tabindex="0"
          role="button"
          v-if="item.diagnosis"
          class="tool-row"
          @click="go(`/pages/practice/practice?id=${id}`)"
          @keydown.enter.prevent="go(`/pages/practice/practice?id=${id}`)"
          @keydown.space.prevent
          @keyup.space.prevent="go(`/pages/practice/practice?id=${id}`)"
        >
          <view class="tool-icon" aria-hidden="true">
            <uni-icons aria-hidden="true" type="compose" size="25" color="var(--color-primary)" />
          </view>
          <text class="tool-label">类似题练习</text>
        </button>
        <button
          tabindex="0"
          role="button"
          class="tool-row"
          @click="go(`/pages/diagnosis/diagnosis?id=${id}`)"
          @keydown.enter.prevent="go(`/pages/diagnosis/diagnosis?id=${id}`)"
          @keydown.space.prevent
          @keyup.space.prevent="go(`/pages/diagnosis/diagnosis?id=${id}`)"
        >
          <view class="tool-icon" aria-hidden="true">
            <uni-icons aria-hidden="true" type="search" size="25" color="var(--color-primary)" />
          </view>
          <text class="tool-label">核对错因</text>
        </button>
        <button
          tabindex="0"
          role="button"
          class="tool-row"
          @click="go(`/pages/knowledge/knowledge?id=${id}`)"
          @keydown.enter.prevent="go(`/pages/knowledge/knowledge?id=${id}`)"
          @keydown.space.prevent
          @keyup.space.prevent="go(`/pages/knowledge/knowledge?id=${id}`)"
        >
          <view class="tool-icon" aria-hidden="true">
            <uni-icons aria-hidden="true" type="map" size="25" color="var(--color-primary)" />
          </view>
          <text class="tool-label">相关知识</text>
        </button>
        <button
          tabindex="0"
          role="button"
          class="tool-row"
          @click="go(paperURL({ subject: item.subject, ids: [id] }))"
          @keydown.enter.prevent="go(paperURL({ subject: item.subject, ids: [id] }))"
          @keydown.space.prevent
          @keyup.space.prevent="go(paperURL({ subject: item.subject, ids: [id] }))"
        >
          <view class="tool-icon" aria-hidden="true">
            <uni-icons aria-hidden="true" type="list" size="25" color="var(--color-primary)" />
          </view>
          <text class="tool-label">用这道题组卷</text>
        </button>
      </view>

      <view
        v-if="section === 'records'"
        class="progress-section"
        @click="go(`/pages/journey/journey?id=${id}`)"
      >
        <text class="section-kicker">学习档案</text>
        <math-text
          class="journey-copy"
          :text="journey?.summary || '查看这道题的诊断、练习和复习记录。'"
          inline
        />
        <view class="learning-path" v-if="journey">
          <view
            v-for="(step, index) in journey.stages"
            :key="step.key"
            :class="{ done: step.completed }"
          >
            <i>
              <uni-icons
                aria-hidden="true"
                v-if="step.completed"
                type="checkmarkempty"
                size="16"
                color="var(--color-primary)"
              />
              <template v-else>{{ index + 1 }}</template>
            </i>
            <text>{{ step.label }}</text>
          </view>
        </view>
        <text class="text-action">
          查看学习记录
          <uni-icons aria-hidden="true" type="right" size="16" color="var(--color-primary)" />
        </text>
      </view>

      <view v-if="section === 'records'" class="secondary-content">
        <view class="fold-row" @click="toggle('student')">
          <text>我的完整步骤</text>
          <uni-icons
            aria-hidden="true"
            :type="opened === 'student' ? 'top' : 'bottom'"
            size="18"
            color="var(--color-text-tertiary)"
          />
        </view>
        <view v-if="opened === 'student'" class="fold-body">
          <view
            v-for="(step, index) in item.student_steps"
            :key="step.id || index"
            class="step-row"
          >
            <i>{{ index + 1 }}</i>
            <math-text :text="step.formula || step.text" />
          </view>
          <text v-if="!item.student_steps?.length" class="muted">还没有识别到完整步骤</text>
        </view>
        <view class="fold-row" @click="toggle('knowledge')">
          <text>知识点</text>
          <uni-icons
            aria-hidden="true"
            :type="opened === 'knowledge' ? 'top' : 'bottom'"
            size="18"
            color="var(--color-text-tertiary)"
          />
        </view>
        <view v-if="opened === 'knowledge'" class="fold-body chip-row">
          <math-text v-for="kp in knowledge" :key="kp" class="tag" :text="kp" inline />
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import MathText from '@/components/math-text/math-text.vue'
import { originalQuestionImage, questionPreviewImages } from '@/utils/question-assets.js'
import { computed, ref } from 'vue'
import { onLoad, onShow, onHide, onUnload } from '@dcloudio/uni-app'
import { deleteData, getData, patchData, postData } from '@/api/index.js'
import { go } from '@/utils/navigation.js'
import { paperURL } from '@/utils/learning.js'
import { requestLearningTask } from '@/utils/task-entry.js'
import { diagnosisView } from '@/utils/diagnosis.js'
const detailSections = [
  { key: 'question', label: '题目与错因' },
  { key: 'learn', label: '解析与练习' },
  { key: 'records', label: '学习记录' },
]
const section = ref('question')
const reviewReturnId = ref('')
const id = ref(''),
  item = ref(null),
  journey = ref(null),
  error = ref(false),
  opened = ref(''),
  busy = ref(false),
  showAnswer = ref(false)
let loading = false,
  active = false,
  revision = 0
const entryError = ref('')
const knowledge = computed(
  () => item.value?.analysis?.knowledge_points || item.value?.knowledge_points || [],
)
const topic = computed(() => knowledge.value[0] || item.value?.question_type || '错题学习')
const mainImage = computed(() => originalQuestionImage(item.value?.assets))
const diagnosisState = computed(() => diagnosisView(item.value))
const firstErrorTitle = computed(() =>
  diagnosisState.value.kind !== 'finding'
    ? ''
    : diagnosisState.value.step
      ? `先核对第 ${diagnosisState.value.step} 步`
      : '先核对本次作答',
)
function optionText(option, index) {
  return typeof option === 'string'
    ? option
    : `${option?.label || option?.key || String.fromCharCode(65 + index)}. ${option?.text || option?.content || option?.value || ''}`
}
async function load() {
  if (!id.value) return
  if (!active || !id.value || loading) return
  const current = ++revision,
    questionId = id.value
  loading = true
  error.value = false
  entryError.value = ''
  item.value = null
  journey.value = null
  try {
    const nextItem = await getData(`/questions/${questionId}`)
    const nextJourney = await getData(`/questions/${questionId}/journey`, { silent: true })
    if (!active || current !== revision) return
    item.value = nextItem
    journey.value = nextJourney
  } catch {
    if (active && current === revision) error.value = true
  } finally {
    if (current === revision) loading = false
  }
}
function preview(url) {
  const assets = questionPreviewImages(item.value.assets)
  uni.previewImage({ urls: assets.map((asset) => asset.url), current: url })
}
function toggle(value) {
  opened.value = opened.value === value ? '' : value
}
async function continueLearning() {
  if (busy.value || !active || !item.value) return
  if (!item.value?.analysis || !item.value?.diagnosis) return continueLegacyLearning()
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
async function continueLegacyLearning() {
  if (busy.value || !active || !item.value) return
  if ((!item.value?.analysis || !item.value?.diagnosis) && journey.value?.next_action) {
    go(journey.value.next_action.url)
    return
  }
  if (!item.value.confirmed) {
    go(`/pages/ocr/ocr?id=${id.value}`)
    return
  }
  if (!item.value.analysis || !item.value.diagnosis) {
    go(`/pages/diagnosis/diagnosis?id=${id.value}`)
    return
  }
  busy.value = true
  entryError.value = ''
  const current = revision,
    questionId = id.value
  try {
    const session = await postData('/tutor/sessions', { question_id: questionId })
    if (active && current === revision) go(`/pages/tutor/tutor?id=${session.id}`)
  } catch (err) {
    if (active && current === revision)
      entryError.value = err.message || '暂时无法开始讲解，请重试。'
  } finally {
    busy.value = false
  }
}
async function toggleFavorite() {
  if (busy.value) return
  busy.value = true
  try {
    const updated = await patchData(`/questions/${id.value}`, { favorite: !item.value.favorite })
    item.value.favorite = updated.favorite
  } catch (err) {
    uni.showToast({ title: err.message || '收藏未保存，请重试', icon: 'none' })
  } finally {
    busy.value = false
  }
}
function showActions() {
  if (!item.value || busy.value) return
  const hasCrop = item.value.assets?.some((asset) => asset.kind === 'crop')
  uni.showActionSheet({
    itemList: [hasCrop ? '重新识别' : '修改题目', '移出错题本'],
    success: async ({ tapIndex }) => {
      if (tapIndex === 0) {
        if (!hasCrop) {
          go(`/pages/ocr/ocr?id=${id.value}&edit=1`)
          return
        }
        busy.value = true
        try {
          const data = await postData(`/questions/${id.value}/reprocess`, {})
          go(`/pages/ocr/ocr?id=${id.value}&job=${data.job_id}`)
        } catch {
        } finally {
          busy.value = false
        }
      } else {
        uni.showModal({
          confirmText: '确定',
          cancelText: '取消',
          title: '移出错题本',
          content: '将取消这道题的待复习任务，历史学习记录会保留。确认移出？',
          success: async ({ confirm }) => {
            if (!confirm) return
            busy.value = true
            try {
              await deleteData(`/questions/${id.value}`)
              uni.reLaunch({ url: '/pages/problem/list' })
            } catch {
            } finally {
              busy.value = false
            }
          },
        })
      }
    },
  })
}
onLoad((q) => {
  id.value = q.id || ''
  reviewReturnId.value = typeof q.review === 'string' && q.review.length <= 80 ? q.review : ''
})
onShow(() => {
  active = true
  load()
})
function leave() {
  active = false
  revision++
  loading = false
  item.value = null
  journey.value = null
}
onHide(leave)
onUnload(leave)
</script>

<style scoped lang="scss">
.icon-action {
  width: 48px;
  min-height: 48px;
  margin: 0;
  padding: 12px;
  background: transparent;
}
.detail-sections {
  display: flex;
  gap: 8px;
  margin-bottom: 20px;
  border-bottom: 1px solid var(--color-border);
}
.detail-sections button {
  flex: 1;
  min-height: 48px;
  margin: 0;
  padding: 12px 6px;
  background: transparent;
  font-size: 16px;
  border-bottom: 2px solid transparent;
  border-radius: 0;
}
.detail-sections button.active {
  color: var(--color-primary);
  border-bottom-color: var(--color-primary);
  font-weight: 600;
}
.detail-status {
  display: block;
  color: var(--color-text-secondary);
  font-size: 14px;
  margin-top: 20px;
}

.detail-page {
  padding-bottom: 20px;
}
.question-section,
.issue-section,
.progress-section {
  padding: 14px 0;
  border-bottom: 0.5px solid var(--color-border);
}
.question-section {
  padding-top: 2px;
}
.detail-figure {
  display: block;
  width: 100%;
  margin: 16px 0;
  border-radius: 8px;
}
.question-image {
  width: 100%;
  max-height: 180px;
  border-radius: 4px;
  background: #fff;
}
.question-text {
  display: block;
  margin-top: 9px;
  color: var(--color-text-primary);
  font-size: 16px;
  font-weight: 500;
  line-height: 1.8;
}
.question-options {
  display: grid;
  gap: 8px;
  margin-top: 10px;
  font-size: 14px;
}
.answer-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0;
  margin-top: 14px;
  border-top: 0.5px solid var(--color-border);
}
.answer-grid > view {
  padding: 11px 8px 0 0;
  min-width: 0;
}
.answer-grid > view + view {
  padding-left: 12px;
}
.answer-grid text {
  display: block;
  margin-bottom: 4px;
  color: var(--color-text-secondary);
  font-size: 13px;
}
.answer-grid :deep(.math-text) {
  font-size: 14px;
  line-height: 1.6;
}
.student-answer {
  color: var(--color-text-primary);
}
.section-kicker {
  display: block;
  color: var(--color-text-secondary);
  font-size: 13px;
  font-weight: 500;
}
.issue-title {
  display: block;
  margin-top: 5px;
  font-size: 16px;
  font-weight: 600;
  line-height: 1.5;
}
.issue-formula {
  display: block;
  margin-top: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  background: var(--color-error-soft);
  font-size: 14px;
}
.issue-reason {
  display: block;
  margin-top: 7px;
  color: var(--color-text-secondary);
  font-size: 13px;
  line-height: 1.7;
}
.text-action {
  display: flex;
  align-items: center;
  gap: 3px;
  min-height: 44px;
  margin-top: 6px;
  color: var(--color-primary);
  font-size: 13px;
}
.journey-copy {
  display: block;
  margin-top: 5px;
  color: var(--color-text-secondary);
  font-size: 13px;
  line-height: 1.7;
}
.learning-path {
  display: flex;
  justify-content: space-between;
  margin-top: 12px;
}
.learning-path > view {
  position: relative;
  flex: 1;
  color: var(--color-text-tertiary);
  font-size: 13px;
  text-align: center;
}
.learning-path > view::after {
  content: '';
  position: absolute;
  top: 10px;
  left: 68%;
  right: -32%;
  height: 0.5px;
  background: var(--color-border);
}
.learning-path > view:last-child::after {
  display: none;
}
.learning-path i {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  margin: 0 auto 5px;
  border-radius: 50%;
  border: 0.5px solid var(--color-border);
  background: #fff;
  font-style: normal;
}
.learning-path .done {
  color: var(--color-text-primary);
}
.learning-path .done i {
  border-color: var(--color-primary);
}
.primary-btn {
  margin-top: 14px;
}
.quiet-action {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  min-height: 44px;
  margin: 4px 0 0;
  padding: 5px 0;
  background: transparent;
  border: 0;
  color: var(--color-primary);
  font-size: 13px;
}
.quiet-action::after {
  border: 0;
}
.secondary-content {
  margin-top: 13px;
  border-top: 0.5px solid var(--color-border);
}
.fold-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 46px;
  border-bottom: 0.5px solid var(--color-border);
  font-size: 14px;
}
.fold-body {
  padding: 9px 0;
}
.step-row {
  display: flex;
  gap: 8px;
  padding: 7px 0;
}
.step-row i {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
  width: 18px;
  height: 20px;
  color: var(--color-text-tertiary);
  font-style: normal;
  font-size: 13px;
}
.step-row :deep(.math-text) {
  font-size: 13px;
  line-height: 1.7;
}

.detail-tools {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}
.learning-tools {
  display: grid;
  gap: 0;
  margin-top: 16px;
  border-top: 1px solid var(--color-border);
}
.tool-row,
.tool-row:last-child,
.without-practice .tool-row:last-child {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  min-height: 60px;
  margin: 0;
  padding: 10px 0;
  border: 0;
  border-bottom: 1px solid var(--color-border);
  border-radius: 0;
  background: transparent;
  text-align: left;
}
.tool-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  flex: none;
}
.tool-label {
  font-size: 15px;
}
.tool-row[disabled] {
  opacity: 0.5;
}
.detail-evidence-entries {
  gap: 16px;
  margin-top: 20px;
  margin-bottom: 0;
}
.question-section {
  background: var(--color-surface);
  padding: 18px;
  border: 1px solid var(--color-border);
  border-radius: 12px;
}
.issue-section {
  padding: 18px 0;
}
.detail-tools {
  gap: 16px;
}
.detail-tools .quiet-action {
  width: auto;
  flex: 1;
  color: var(--color-text-secondary);
}
</style>
