<template>
  <view class="page task-page">
    <app-header :title="id ? '本题学习' : '学习记录'" back>
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
          <text class="history-title">{{ item.question_title || '本题学习' }}</text>
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
          <text class="task-title">{{ task.student_view?.title }}</text>
          <view
            v-if="
              task.student_view?.feedback && !handwritingId && !task.student_view?.visualization
            "
            class="feedback"
          >
            <math-text :text="task.student_view.feedback" />
          </view>
          <teaching-content
            v-if="!task.student_view?.visualization"
            :blocks="task.student_view?.prompt_blocks || []"
          />
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
            <text class="answer-label">写下你的回答</text>
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
              v-model="answer"
              class="answer-input"
              aria-label="写下你的回答"
              placeholder="可以写算式，也可以补充依据"
              :maxlength="12000"
              :disabled="sending || !!pending"
              auto-height
            />
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
                    : '提交'
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
              给点提示
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
              {{ showMoreWays ? '收起更多方式' : '更多方式' }}
            </button>
          </view>
          <view
            v-if="moreWaysAvailable"
            v-show="showMoreWays"
            :id="`task-help-${task.id}`"
            class="more-ways"
            role="region"
            aria-label="更多作答与学习方式"
          >
            <button
              v-if="task.student_view?.input_kind === 'text' && canCancel"
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
              用图看看
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
            class="primary-btn"
            role="button"
            tabindex="0"
            @click="returnToQuestion(task.question_id)"
            @keydown.enter.prevent="returnToQuestion(task.question_id)"
          >
            回到原题
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
import { computed, ref, watch } from 'vue'
import TeachingContent from '@/components/teaching-content/teaching-content.vue'
import SelfCheck from '@/components/self-check/self-check.vue'
import TaskHistory from '@/components/task-history/task-history.vue'
import TaskVisualization from '@/components/task-visualization/task-visualization.vue'
import FigureReview from '@/components/figure-review/figure-review.vue'
import { onLoad, onShow, onHide, onUnload } from '@dcloudio/uni-app'
import { getData, postData, uploadFile } from '@/api/index.js'
import { go, returnToQuestion } from '@/utils/navigation.js'
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
const moreWaysAvailable = computed(
  () =>
    !task.value?.student_view?.visualization &&
    ((task.value?.student_view?.input_kind === 'text' && canCancel.value) ||
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
    text: kind === 'answer' ? answer.value : '',
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
    title: '用图看看',
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
.task-page {
  padding-bottom: calc(24px + env(safe-area-inset-bottom));
}
.context-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 20px;
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
  font-size: 22px;
  font-weight: 600;
  line-height: 1.5;
  margin-bottom: 20px;
}
.feedback {
  margin: 16px 0;
  padding: 16px;
  background: var(--color-surface);
  border-left: 3px solid var(--color-primary);
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
  min-height: 96px;
  padding: 16px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  font-size: 16px;
  line-height: 1.6;
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
