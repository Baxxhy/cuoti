<template>
  <view class="page task-page">
    <app-header :title="id ? '错题订正' : '订正记录'" back>
      <button
        v-if="task && canCancel && !task.restart_required"
        class="text-action"
        role="button"
        tabindex="0"
        aria-label="结束本次学习"
        :disabled="sending"
        @click="cancel"
        @keydown.enter.prevent="cancel"
      >
        结束
      </button>
    </app-header>
    <view class="page-content">
      <state-panel v-if="loading && !task" state="loading" />
      <view v-if="error" class="error-note" role="alert">
        <text>{{ error }}</text>
        <button
          class="secondary-btn"
          role="button"
          tabindex="0"
          @click="load"
          @keydown.enter.prevent="load"
        >
          核对提交状态
        </button>
      </view>
      <text v-if="draftWarning && canCancel" class="muted" role="status">{{ draftWarning }}</text>
      <template v-if="!id && !loading">
        <view v-if="!history.length" class="empty">
          <text>还没有订正学习记录</text>
          <button class="secondary-btn" role="button" @click="go('/pages/problem/list')">
            从一道错题开始
          </button>
        </view>
        <button
          v-for="item in history"
          :key="item.id"
          class="history-item"
          role="button"
          tabindex="0"
          @click="go(`/pages/task/task?id=${item.id}`)"
          @keydown.enter.prevent="go(`/pages/task/task?id=${item.id}`)"
        >
          <math-text class="history-title" :text="item.question_title || '错题订正'" inline />
          <text class="muted">{{ taskStatusLabel(item.status) }}</text>
        </button>
      </template>
      <template v-if="task">
        <view class="context-row">
          <text class="muted" aria-live="polite">
            {{ task.restart_required ? '可以重新开始' : taskStatusLabel(task.status) }}
          </text>
          <button
            class="text-action"
            role="button"
            tabindex="0"
            @click="returnToQuestion(task.question_id)"
            @keydown.enter.prevent="returnToQuestion(task.question_id)"
          >
            查看原题
          </button>
        </view>
        <view v-if="processing" class="waiting" role="status">
          <text>
            {{
              task.current_action === 'recognize_handwriting'
                ? task.status === 'queued'
                  ? '照片已保存，等待识别'
                  : '正在识别作答照片'
                : task.status === 'queued'
                  ? '正在准备这一步'
                  : '正在核对这一步'
            }}
          </text>
          <text class="muted">可以离开，稍后从这里继续。</text>
        </view>
        <template v-else>
          <math-text class="task-title" :text="taskTitle" inline />
          <view
            v-if="taskFeedback && !handwritingId && !task.student_view?.visualization"
            class="feedback"
          >
            <math-text :text="taskFeedback" />
          </view>
          <teaching-content
            v-if="!task.student_view?.visualization"
            :blocks="task.student_view?.prompt_blocks || []"
            :selectable="canChoose"
            :answer="answer"
            :disabled="sending || !!pending"
            @choose="answer = $event"
          />
          <view
            v-if="
              task.student_view?.recommendation &&
              ((task.status === 'completed' &&
                (task.student_view.recommendation.question_id ||
                  task.student_view.recommendation.knowledge_card_ids?.length)) ||
                task.student_view.recommendation.action === 'prerequisite')
            "
            class="recommendation-note"
          >
            <text>{{ task.student_view.recommendation.reason }}</text>
            <button
              v-if="task.status === 'completed' && task.student_view.recommendation.question_id"
              class="primary-btn"
              role="button"
              tabindex="0"
              :disabled="sending"
              @click="startRecommendation"
              @keydown.enter.prevent="startRecommendation"
            >
              {{ task.student_view.recommendation.action === 'review' ? '开始复习' : '练习推荐题' }}
            </button>
            <button
              v-else-if="
                (task.status === 'completed' ||
                  task.student_view.recommendation.action === 'prerequisite') &&
                task.student_view.recommendation.knowledge_card_ids?.length
              "
              class="secondary-btn"
              role="button"
              tabindex="0"
              @keydown.enter.prevent="openRecommendedKnowledge"
              @click="openRecommendedKnowledge"
            >
              查看相关知识
            </button>
          </view>
          <view
            v-if="
              task.student_view?.diagnosis_evidence &&
              task.exit_reason === 'diagnosis_needs_confirmation'
            "
            class="diagnosis-evidence"
          >
            <text>
              {{ task.student_view.diagnosis_evidence.verified ? '步骤核验结果' : '需要核对' }}
            </text>
            <math-text :text="task.student_view.diagnosis_evidence.reason" />
            <view
              v-for="(source, index) in task.student_view.diagnosis_evidence.evidence"
              :key="index"
            >
              <math-text :text="source.text" />
            </view>
          </view>
          <button
            v-if="task.exit_reason === 'diagnosis_needs_confirmation'"
            class="primary-btn"
            role="button"
            tabindex="0"
            @click="go(`/pages/diagnosis/diagnosis?id=${task.question_id}`)"
            @keydown.enter.prevent="go(`/pages/diagnosis/diagnosis?id=${task.question_id}`)"
          >
            核对原作答与错因
          </button>
          <task-visualization
            v-if="task.student_view?.visualization"
            :packet="task.student_view.visualization"
            :task-id="task.id"
            :fingerprint="task.input_fingerprint"
            :step-id="task.step_id"
            :busy="sending || !!pending"
            @save="saveVisual"
            @close="send('close_visualization')"
          />
          <template
            v-if="
              task.student_view?.input_kind === 'text' &&
              canCancel &&
              !task.student_view?.visualization
            "
          >
            <view v-if="previousDraft?.text" class="previous-draft">
              <button
                class="text-action"
                role="button"
                :aria-expanded="showPreviousDraft"
                tabindex="0"
                @keydown.enter.prevent="showPreviousDraft = !showPreviousDraft"
                @click="showPreviousDraft = !showPreviousDraft"
              >
                上一步草稿
                <text>{{ showPreviousDraft ? '收起' : '查看' }}</text>
              </button>
              <view v-if="showPreviousDraft">
                <math-text :text="previousDraft.text" />
                <text class="muted">这是旧步骤的文字，请先核对当前题目。</text>
                <button
                  class="text-action"
                  role="button"
                  :disabled="sending || !!pending"
                  tabindex="0"
                  @keydown.enter.prevent="restorePreviousDraft"
                  @click="restorePreviousDraft"
                >
                  放入当前输入
                </button>
              </view>
            </view>
            <text v-if="!canChoose" class="answer-label" id="task-answer-label">我的作答</text>
            <view v-if="handwritingId" class="photo-note">
              <text>
                {{
                  !task.student_view.handwriting?.suggested_text
                    ? '没有识别到文字，原先输入已保留。'
                    : task.student_view.handwriting?.recognition?.uncertain
                      ? '部分字迹不清晰，可先修改文字。'
                      : '核对这次文字，再确认提交。'
                }}
              </text>
              <view class="photo-actions">
                <button
                  class="text-action"
                  role="button"
                  tabindex="0"
                  @click="previewPhoto"
                  @keydown.enter.prevent="previewPhoto"
                >
                  查看作答照片
                </button>
                <button
                  class="text-action"
                  role="button"
                  tabindex="0"
                  @click="useTextOnly"
                  @keydown.enter.prevent="useTextOnly"
                >
                  仅用文字作答
                </button>
              </view>
              <figure-review :rows="task.student_view.handwriting?.figure_review || []" />
            </view>
            <textarea
              v-if="!canChoose"
              v-model="answer"
              class="answer-input"
              aria-label="我的作答"
              aria-labelledby="task-answer-label"
              placeholder="输入答案或解题步骤"
              :maxlength="12000"
              :disabled="sending || !!pending"
              :cursor="mathCursor"
              :focus="mathFocus"
              @input="rememberMathCursor"
              @blur="rememberMathCursor"
              auto-height
            />
            <view v-if="!canChoose" class="task-math-tools">
              <button
                role="button"
                :disabled="sending || !!pending"
                :aria-expanded="mathOpen"
                @click="mathOpen = !mathOpen"
              >
                数学符号
              </button>
              <view v-if="mathOpen" class="task-math-keys">
                <button
                  v-for="key in mathKeys"
                  :key="key.label"
                  role="button"
                  :disabled="sending || !!pending"
                  @click="insertMath(key)"
                >
                  {{ key.label }}
                </button>
              </view>
            </view>
            <button
              class="primary-btn"
              role="button"
              tabindex="0"
              :disabled="sending || !!pending || !answer.trim()"
              :aria-disabled="sending || !!pending || !answer.trim()"
              @click="send('answer')"
              @keydown.enter.prevent="send('answer')"
            >
              {{
                sending
                  ? pending?.kind === 'recognize_handwriting'
                    ? '正在上传照片…'
                    : '正在保存…'
                  : handwritingId
                    ? '确认文字并提交'
                    : '提交作答'
              }}
            </button>
            <button
              v-if="previousAnswer && handwritingId"
              class="text-action"
              role="button"
              @click="restoreAnswer"
            >
              恢复上传前的文字
            </button>
          </template>
          <button
            v-if="pending && !processing"
            class="secondary-btn"
            role="button"
            @click="retryPending"
          >
            重试刚才的提交
          </button>
          <button
            v-if="pending?.kind === 'recognize_handwriting' && !processing"
            class="text-action"
            role="button"
            tabindex="0"
            :disabled="sending"
            @click="reselectPhoto"
            @keydown.enter.prevent="reselectPhoto"
          >
            核对状态后重新选图
          </button>
          <view v-if="!task.student_view?.visualization" class="secondary-actions">
            <button
              v-if="task.student_view?.secondary_actions?.includes('use_text')"
              class="text-action"
              role="button"
              tabindex="0"
              :disabled="sending || !!pending"
              @click="send('use_text')"
              @keydown.enter.prevent="send('use_text')"
            >
              改用文字作答
            </button>
            <button
              v-if="task.student_view?.secondary_actions?.includes('hint')"
              class="text-action"
              role="button"
              tabindex="0"
              :disabled="sending || !!pending"
              @click="send('hint')"
              @keydown.enter.prevent="send('hint')"
            >
              {{ task.student_view?.hint_level ? '下一条提示' : '查看提示' }}
            </button>
            <button
              v-if="task.student_view?.secondary_actions?.includes('resume')"
              class="text-action"
              role="button"
              tabindex="0"
              :disabled="sending || !!pending"
              @click="send('resume')"
              @keydown.enter.prevent="send('resume')"
            >
              继续核对
            </button>
            <button
              v-if="moreWaysAvailable"
              class="text-action"
              role="button"
              tabindex="0"
              :aria-expanded="showMoreWays"
              :aria-controls="`task-help-${task.id}`"
              :disabled="sending || !!pending"
              @click="showMoreWays = !showMoreWays"
              @keydown.enter.prevent="showMoreWays = !showMoreWays"
            >
              {{ showMoreWays ? '收起辅助工具' : canChoose ? '答案与辅助工具' : '拍照与辅助工具' }}
            </button>
          </view>
          <view
            v-if="moreWaysAvailable"
            v-show="showMoreWays"
            :id="`task-help-${task.id}`"
            class="more-ways"
            role="region"
            :aria-label="canChoose ? '答案与辅助工具' : '拍照与辅助工具'"
          >
            <button
              v-if="task.student_view?.input_kind === 'text' && canCancel && !canChoose"
              class="text-action"
              role="button"
              tabindex="0"
              :disabled="sending || !!pending"
              @click="choosePhoto"
              @keydown.enter.prevent="choosePhoto"
            >
              拍照或选图作答
            </button>
            <button
              v-if="task.student_view?.secondary_actions?.includes('visualize')"
              class="text-action"
              role="button"
              tabindex="0"
              :disabled="sending || !!pending"
              @click="openVisual"
              @keydown.enter.prevent="openVisual"
            >
              查看图解
            </button>
            <button
              v-if="task.student_view?.secondary_actions?.includes('reveal')"
              class="text-action"
              role="button"
              tabindex="0"
              :disabled="sending || !!pending"
              @click="reveal"
              @keydown.enter.prevent="reveal"
            >
              查看参考答案
            </button>
          </view>
          <view
            v-if="!processing && task.student_view?.input_kind !== 'text' && retainedDraft.trim()"
            class="retained-draft"
          >
            <button
              class="text-action"
              role="button"
              tabindex="0"
              :aria-expanded="showRetainedDraft"
              @click="showRetainedDraft = !showRetainedDraft"
              @keydown.enter.prevent="showRetainedDraft = !showRetainedDraft"
            >
              本机未提交草稿 {{ showRetainedDraft ? '收起' : '查看' }}
            </button>
            <math-text v-if="showRetainedDraft" :text="retainedDraft" />
          </view>
          <button
            v-if="task.restart_required && canCancel"
            class="primary-btn"
            role="button"
            tabindex="0"
            :disabled="sending"
            @click="cancel(true)"
            @keydown.enter.prevent="cancel(true)"
          >
            结束并回原题
          </button>
          <button
            v-if="!canCancel"
            :class="
              task.student_view?.recommendation?.question_id ? 'secondary-btn' : 'primary-btn'
            "
            role="button"
            tabindex="0"
            @click="returnToQuestion(task.question_id)"
            @keydown.enter.prevent="returnToQuestion(task.question_id)"
          >
            回到原题
          </button>
          <button
            v-if="task.status === 'completed' && !task.student_view?.recommendation?.question_id"
            class="secondary-btn"
            role="button"
            tabindex="0"
            @click="go(`/pages/practice/practice?id=${encodeURIComponent(task.question_id)}`)"
            @keydown.enter.prevent="
              go(`/pages/practice/practice?id=${encodeURIComponent(task.question_id)}`)
            "
          >
            练一道类似题
          </button>
          <self-check
            v-if="['completed', 'stale'].includes(task.status)"
            :key="task.id"
            :task="task"
          />
        </template>
        <task-history :key="task.id" :task="task" />
      </template>
    </view>
  </view>
</template>
<script setup>
import { learningFeedback } from '@/utils/learning-feedback.js'
import MathText from '@/components/math-text/math-text.vue'
import { computed, nextTick, ref, watch } from 'vue'
import TeachingContent from '@/components/teaching-content/teaching-content.vue'
import SelfCheck from '@/components/self-check/self-check.vue'
import TaskHistory from '@/components/task-history/task-history.vue'
import TaskVisualization from '@/components/task-visualization/task-visualization.vue'
import FigureReview from '@/components/figure-review/figure-review.vue'
import { onLoad, onShow, onHide, onUnload } from '@dcloudio/uni-app'
import { getData, postData, uploadFile } from '@/api/index.js'
import { go, returnToQuestion } from '@/utils/navigation.js'
import { mathKeys, insertMathText } from '@/utils/math-input.js'
import { useAppStore } from '@/store/index.js'
import {
  readTaskDraft,
  saveTaskDraft,
  taskRequestId,
  taskStatusLabel,
  reconcileTaskDraft,
  advanceTaskDraft,
} from '@/utils/task-draft.js'
const store = useAppStore()
const mathOpen = ref(false),
  mathCursor = ref(-1),
  mathFocus = ref(false)
let inputCursor = null
function rememberMathCursor(event) {
  const cursor = event.detail?.cursor ?? event.target?.selectionStart
  if (Number.isInteger(cursor)) inputCursor = cursor
}
async function insertMath(key) {
  if (sending.value || pending.value) return
  const result = insertMathText(answer.value, key, inputCursor, 12000)
  if (!result) return
  mathFocus.value = false
  answer.value = result.value
  inputCursor = result.cursor
  await nextTick()
  mathCursor.value = result.cursor
  mathFocus.value = true
}
const draftWarning = ref(''),
  previousDraft = ref(null),
  showPreviousDraft = ref(false),
  showRetainedDraft = ref(false),
  showMoreWays = ref(false)
const id = ref(''),
  task = ref(null),
  history = ref([]),
  loading = ref(true),
  error = ref(''),
  answer = ref(''),
  pending = ref(null),
  sending = ref(false)
const taskTitle = computed(() =>
  task.value?.student_view?.title === '独立完成这道题'
    ? '重新作答'
    : task.value?.student_view?.title === '换个条件，再试一次'
      ? '再练一道'
      : task.value?.student_view?.title,
)
const taskFeedback = computed(() => {
  const view = task.value?.student_view
  // This fixed transition repeats the heading; retain all actual answer feedback.
  if (
    task.value?.status === 'waiting_student' &&
    view?.title === '换个条件，再试一次' &&
    view?.feedback === '原题的结论已核对。现在换一个条件，独立试一次。'
  )
    return ''
  return learningFeedback(view?.feedback)
})
const processing = computed(() => ['queued', 'running'].includes(task.value?.status))
const retainedDraft = computed(() =>
  answer.value.trim() ? answer.value : previousDraft.value?.text || '',
)
const handwritingId = ref(''),
  seenHandwriting = ref(''),
  previousAnswer = ref('')
const canCancel = computed(() =>
  ['queued', 'running', 'waiting_student', 'needs_review', 'failed'].includes(task.value?.status),
)
const canChoose = computed(
  () =>
    task.value?.student_view?.input_kind === 'text' &&
    canCancel.value &&
    !handwritingId.value &&
    (task.value?.student_view?.prompt_blocks || []).some(
      (block) => block.kind === 'question' && block.options?.length,
    ),
)
const moreWaysAvailable = computed(
  () =>
    !task.value?.student_view?.visualization &&
    ((task.value?.student_view?.input_kind === 'text' && canCancel.value && !canChoose.value) ||
      task.value?.student_view?.secondary_actions?.some((kind) =>
        ['visualize', 'reveal'].includes(kind),
      )),
)
let visible = false,
  timer,
  epoch = 0
function saveDraft() {
  if (task.value && store.user?.id) {
    const saved = saveTaskDraft(store.user.id, id.value, {
      fingerprint: task.value.input_fingerprint,
      step_id: task.value.step_id,
      previous_draft: previousDraft.value,
      text: answer.value,
      pending: pending.value,
      handwriting_id: handwritingId.value,
      seen_handwriting: seenHandwriting.value,
      previous_answer: previousAnswer.value,
    })
    draftWarning.value = saved ? '' : '本机暂时无法保存未提交的草稿，请先提交再离开。'
  }
}
watch(answer, saveDraft)
function schedule() {
  clearTimeout(timer)
  if (visible && processing.value) timer = setTimeout(load, 1200)
}
async function load() {
  const current = ++epoch
  error.value = ''
  try {
    if (!store.user) await store.loadUser()
    if (!id.value) {
      history.value = await getData('/learning-tasks')
      return
    }
    const value = await getData(`/learning-tasks/${id.value}`, { silent: true })
    if (current !== epoch || !visible) return
    const draft =
      draftWarning.value && task.value?.input_fingerprint === value.input_fingerprint
        ? {
            step_id: task.value.step_id,
            previous_draft: previousDraft.value,
            text: answer.value,
            pending: pending.value,
            handwriting_id: handwritingId.value,
            seen_handwriting: seenHandwriting.value,
            previous_answer: previousAnswer.value,
          }
        : readTaskDraft(store.user.id, id.value, value.input_fingerprint)
    const reconciled = reconcileTaskDraft(draft, value)
    if (reconciled.ownTransition)
      advanceTaskDraft(store.user.id, `visual:${id.value}`, reconciled.fromStep, value.step_id)
    if (task.value?.step_id !== value.step_id) showMoreWays.value = false
    task.value = value
    answer.value = reconciled.draft.text || ''
    pending.value = reconciled.draft.pending || null
    handwritingId.value = reconciled.draft.handwriting_id || ''
    seenHandwriting.value = reconciled.draft.seen_handwriting || ''
    previousAnswer.value = reconciled.draft.previous_answer || ''
    previousDraft.value = reconciled.draft.previous_draft || null
    if (reconciled.changed) {
      showPreviousDraft.value = false
      error.value = '这一步已有更新，旧草稿已单独保留，请先核对当前题目。'
    }
    saveDraft()
    const photo = value.student_view?.handwriting
    if (photo?.id && photo.id !== seenHandwriting.value) {
      previousAnswer.value = answer.value
      seenHandwriting.value = photo.id
      handwritingId.value = photo.id
      if (photo.suggested_text) answer.value = photo.suggested_text
      saveDraft()
    } else if (!photo?.id && !processing.value) {
      handwritingId.value = ''
      seenHandwriting.value = ''
      previousAnswer.value = ''
      saveDraft()
    }
    schedule()
    return true
  } catch (err) {
    if (current === epoch) error.value = err.message || '暂时无法读取，回答已保留'
  } finally {
    loading.value = false
  }
}
async function transmit(body) {
  if (sending.value) return
  sending.value = true
  error.value = ''
  pending.value = body
  saveDraft()
  try {
    if (body.kind === 'recognize_handwriting') {
      await uploadFile(`/learning-tasks/${id.value}/handwriting`, body.file_path, 'file', {
        version: body.version,
        step_id: body.step_id,
        input_fingerprint: body.input_fingerprint,
        request_id: body.request_id,
      })
    } else await postData(`/learning-tasks/${id.value}/actions`, body, { silent: true })
    await load()
  } catch (err) {
    error.value = err.message || '连接中断，回答已保留，请核对提交状态'
  } finally {
    sending.value = false
  }
}
function openRecommendedKnowledge() {
  const cardId = task.value?.student_view?.recommendation?.knowledge_card_ids?.[0]
  if (!cardId) return
  go(
    `/pages/library/library?code=${encodeURIComponent(cardId)}&question=${encodeURIComponent(task.value.question_id)}`,
  )
}
async function startRecommendation() {
  const plan = task.value?.student_view?.recommendation
  if (!plan?.question_id || sending.value) return
  if (plan.question_source === 'notebook') {
    returnToQuestion(plan.question_id)
    return
  }
  sending.value = true
  error.value = ''
  try {
    const session = await postData(
      '/study-sessions',
      {
        mode: 'practice',
        question_ids: [plan.question_id],
        learning_task_id: task.value.id,
        count: 1,
        selection_strategy: 'random',
        minutes: Math.max(1, plan.estimated_minutes || 3),
      },
      { silent: true },
    )
    go(`/pages/study-session/study-session?id=${session.id}`)
  } catch (err) {
    error.value = err.message || '暂时无法开始，请重试'
  } finally {
    sending.value = false
  }
}
function send(kind) {
  if (
    sending.value ||
    pending.value ||
    processing.value ||
    !task.value ||
    (kind === 'answer' && !answer.value.trim())
  )
    return
  transmit({
    kind,
    text: kind === 'answer' || kind === 'hint' ? answer.value : '',
    version: task.value.version,
    step_id: task.value.step_id,
    input_fingerprint: task.value.input_fingerprint,
    request_id: taskRequestId(),
    ...(kind === 'answer' && handwritingId.value
      ? { handwriting_id: handwritingId.value, handwriting_confirmed: true }
      : {}),
  })
}
function restorePreviousDraft() {
  if (sending.value || pending.value || !previousDraft.value?.text) return
  const text = previousDraft.value.text,
    stepId = task.value.step_id
  uni.showModal({
    title: '使用旧草稿',
    content: '请确认这段文字适用于当前步骤；当前输入会被替换。',
    confirmText: '使用文字',
    success: ({ confirm }) => {
      if (!confirm || sending.value || pending.value || task.value.step_id !== stepId) return
      answer.value = text
      saveDraft()
    },
  })
}
function choosePhoto() {
  if (sending.value || pending.value || processing.value || !canCancel.value) return
  const source = {
    version: task.value.version,
    step_id: task.value.step_id,
    input_fingerprint: task.value.input_fingerprint,
  }
  uni.chooseImage({
    count: 1,
    sizeType: ['original'],
    sourceType: ['camera', 'album'],
    success: ({ tempFilePaths }) => {
      if (
        !tempFilePaths?.[0] ||
        !visible ||
        sending.value ||
        pending.value ||
        source.step_id !== task.value.step_id
      )
        return
      transmit({
        ...source,
        kind: 'recognize_handwriting',
        file_path: tempFilePaths[0],
        request_id: taskRequestId(),
      })
    },
  })
}
async function previewPhoto() {
  if (!(await load())) return
  const url = task.value?.student_view?.handwriting?.image_url
  if (url) uni.previewImage({ urls: [url], current: url })
}
function useTextOnly() {
  if (sending.value || pending.value || processing.value) return
  handwritingId.value = ''
  saveDraft()
}
function restoreAnswer() {
  if (sending.value || pending.value || processing.value) return
  answer.value = previousAnswer.value
  handwritingId.value = ''
  saveDraft()
}
function retryPending() {
  if (pending.value) transmit({ ...pending.value })
}
function openVisual() {
  if (sending.value || pending.value || processing.value) return
  uni.showModal({
    title: '查看图解',
    content: '这次会记录为辅助学习。',
    confirmText: '查看',
    success: ({ confirm }) => {
      if (confirm) send('visualize')
    },
  })
}
function saveVisual({ values, text }) {
  if (sending.value || pending.value || processing.value || !text.trim()) return
  transmit({
    kind: 'observe_visualization',
    text,
    visual_values: values,
    version: task.value.version,
    step_id: task.value.step_id,
    input_fingerprint: task.value.input_fingerprint,
    request_id: taskRequestId(),
  })
}
async function reselectPhoto() {
  if (sending.value || pending.value?.kind !== 'recognize_handwriting') return
  const request = pending.value.request_id
  const checked = await load()
  if (!checked) return
  if (
    pending.value?.request_id === request &&
    task.value.version === pending.value.version &&
    task.value.last_request_id !== request &&
    ['waiting_student', 'needs_review'].includes(task.value.status)
  ) {
    pending.value = null
    saveDraft()
    choosePhoto()
  }
}
function reveal() {
  if (sending.value || pending.value || processing.value || !canCancel.value) return
  uni.showModal({
    title: '查看参考答案',
    content: '看过答案后，这次会记为辅助学习。',
    confirmText: '查看',
    success: ({ confirm }) => {
      if (confirm) send('reveal')
    },
  })
}
function cancel(returnAfter = false) {
  if (sending.value) return
  uni.showModal({
    title: '结束这次学习？',
    content: '记录会保留。之后可以从原题重新开始。',
    success: async ({ confirm }) => {
      if (!confirm) return
      sending.value = true
      try {
        await postData(`/learning-tasks/${id.value}/cancel`, {})
        await load()
        if (returnAfter === true && task.value?.status === 'cancelled')
          returnToQuestion(task.value.question_id)
      } catch {
        error.value = '暂时未能确认结束状态，请核对后重试。'
      } finally {
        sending.value = false
      }
    },
  })
}
onLoad((q) => {
  id.value = q.id || ''
})
onShow(() => {
  visible = true
  load()
})
function stop() {
  visible = false
  epoch++
  clearTimeout(timer)
  saveDraft()
}
onHide(stop)
onUnload(stop)
</script>
<style scoped lang="scss">
.task-math-tools {
  margin: 2px 0 8px;
}
.task-math-tools > button {
  margin: 0;
  padding: 8px 0;
  min-height: 44px;
  font-size: 13px;
  text-align: left;
  color: var(--color-text-secondary);
  background: transparent;
}
.task-math-keys {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.task-math-keys button {
  margin: 0;
  padding: 8px 12px;
  min-height: 44px;
  min-width: 44px;
  font-size: 15px;
  border-radius: 8px;
  background: var(--color-surface-subtle);
}
.task-page {
  padding-bottom: calc(24px + env(safe-area-inset-bottom));
}
.context-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}
.text-action {
  min-height: 48px;
  margin: 0;
  padding: 12px 6px;
  background: transparent;
  color: var(--color-primary);
  font-size: 14px;
}
.task-title {
  display: block;
  font-size: 18px;
  font-weight: 600;
  line-height: 1.5;
  margin-bottom: 14px;
}
.feedback,
.recommendation-note,
.diagnosis-evidence {
  margin: 16px 0;
  padding: 16px;
  background: var(--color-primary-soft);
  border-radius: var(--radius-card);
  font-size: 16px;
}
.answer-label {
  display: block;
  font-size: 14px;
  margin: 24px 0 10px;
}
.photo-note {
  padding: 12px 0;
  color: var(--color-text-secondary);
  font-size: 14px;
  line-height: 1.6;
}
.photo-actions {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}
.answer-input {
  width: 100%;
  min-height: 132px;
  padding: 16px;
  background: var(--color-surface);
  border: 1px solid var(--color-primary-border);
  border-radius: 10px;
  font-size: 16px;
  line-height: 1.6;
}
.answer-input:focus-within {
  border-color: var(--color-primary);
  outline: none;
  box-shadow: none;
}
.secondary-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 12px;
  margin-top: 12px;
}
.more-ways {
  margin-top: 8px;
  padding: 8px 0;
  border-top: 1px solid var(--color-border);
}
.more-ways .text-action {
  width: 100%;
  text-align: left;
}
.waiting {
  display: grid;
  gap: 12px;
  padding: 24px 0;
}
.error-note {
  color: var(--color-error);
  padding: 12px 0;
}
.history-item {
  width: 100%;
  padding: 18px 0;
  margin: 0;
  border-radius: 0;
  text-align: left;
  background: transparent;
  border-bottom: 1px solid var(--color-border);
}
.history-title {
  display: block;
  font-size: 16px;
  line-height: 1.6;
  margin-bottom: 6px;
}
</style>
