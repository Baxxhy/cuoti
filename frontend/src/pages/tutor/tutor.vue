<template>
  <view class="tutor-page">
    <app-header title="AI 讲解" back>
      <button
        tabindex="0"
        role="button"
        v-if="session"
        class="context-action"
        :aria-expanded="questionOpen"
        @click="questionOpen = !questionOpen"
        @keydown.enter.prevent="questionOpen = !questionOpen"
        @keydown.space.prevent
        @keyup.space.prevent="questionOpen = !questionOpen"
      >
        题目
      </button>
      <button
        tabindex="0"
        role="button"
        v-if="session"
        class="context-action"
        :aria-expanded="planOpen"
        @click="planOpen = !planOpen"
        @keydown.enter.prevent="planOpen = !planOpen"
        @keydown.space.prevent
        @keyup.space.prevent="planOpen = !planOpen"
      >
        进度
      </button>
    </app-header>
    <state-panel
      v-if="!session"
      :state="!id || error ? 'error' : 'loading'"
      :message="!id ? '请先选择一道错题' : undefined"
      :retry-text="!id ? '选择错题' : '重新加载'"
      @retry="id ? load() : go('/pages/problem/list')"
    />

    <template v-else>
      <view v-if="planOpen" class="stage-strip">
        <view
          v-for="(label, index) in visibleStages"
          :key="label"
          :class="{
            active: index === visibleStageIndex,
            done: index < visibleStageIndex,
            backable: canRewind && index === visibleStageIndex - 1,
          }"
          @click="rewindFromStage(index)"
        >
          <i>
            <uni-icons
              aria-hidden="true"
              v-if="index < visibleStageIndex"
              type="checkmarkempty"
              size="14"
              color="var(--color-primary)"
            />
            <template v-else>{{ index + 1 }}</template>
          </i>
          <text>{{ label }}</text>
        </view>
      </view>

      <scroll-view scroll-y class="task-scroll">
        <view class="task-content">
          <view v-if="questionOpen" class="question-context">
            <math-text :text="session.question?.text || '题目暂时无法读取'" inline />
            <button
              tabindex="0"
              role="button"
              class="context-action"
              @click="questionOpen = false"
              @keydown.enter.prevent="questionOpen = false"
              @keydown.space.prevent
              @keyup.space.prevent="questionOpen = false"
            >
              收起题目
            </button>
          </view>
          <button
            :aria-disabled="busy"
            :tabindex="busy ? -1 : 0"
            role="button"
            v-if="canRewind"
            class="rewind-button"
            :disabled="busy"
            @click="rewindStage"
            @keydown.enter.prevent="!busy && rewindStage"
            @keydown.space.prevent
            @keyup.space.prevent="!busy && rewindStage"
          >
            <i />
            返回上一步 · {{ visibleStages[visibleStageIndex - 1] }}
          </button>
          <view v-if="session.stage !== 'finished' && !activity" class="teacher-intro">
            <text>小智老师</text>
            <b><math-text :text="introText" inline /></b>
          </view>

          <view v-if="activity" class="activity-card">
            <template v-if="isAnswerReveal">
              <view class="answer-brief-heading">
                <math-text :text="answerReveal.topic" inline />
                <b>答案对照</b>
              </view>
              <view class="answer-compare">
                <view>
                  <text>你的答案</text>
                  <b class="student-answer">
                    <math-text :text="answerReveal.student_answer" inline />
                  </b>
                </view>
                <view>
                  <text>正确答案</text>
                  <b class="correct-answer">
                    <math-text :text="answerReveal.correct_answer" inline />
                  </b>
                </view>
              </view>
              <view class="why-block">
                <b><math-text :text="'为什么是' + answerReveal.correct_answer + '？'" inline /></b>
                <math-text
                  v-if="answerReveal.key_explanation"
                  :text="answerReveal.key_explanation"
                  inline
                />
                <view v-if="answerReveal.option_explanations?.length" class="option-explanations">
                  <view
                    v-for="item in answerReveal.option_explanations"
                    :key="item.label"
                    :class="{ correct: item.correct }"
                  >
                    <i>{{ item.label }}</i>
                    <math-text :text="item.text" inline />
                    <b v-if="item.correct">正确</b>
                  </view>
                </view>
              </view>
              <view class="brief-actions">
                <button
                  :aria-disabled="busy"
                  :tabindex="busy ? -1 : 0"
                  role="button"
                  class="primary-btn"
                  :disabled="busy"
                  @click="acknowledgeBrief('understood')"
                  @keydown.enter.prevent="!busy && acknowledgeBrief('understood')"
                  @keydown.space.prevent
                  @keyup.space.prevent="!busy && acknowledgeBrief('understood')"
                >
                  开始练习
                </button>
                <button
                  :aria-disabled="busy"
                  :tabindex="busy ? -1 : 0"
                  role="button"
                  class="secondary-btn"
                  :disabled="busy"
                  @click="acknowledgeBrief('need_help')"
                  @keydown.enter.prevent="!busy && acknowledgeBrief('need_help')"
                  @keydown.space.prevent
                  @keyup.space.prevent="!busy && acknowledgeBrief('need_help')"
                >
                  这里我还不明白
                </button>
              </view>
            </template>

            <template v-else>
              <view
                v-if="answerReveal.correct_answer && session.stage === 'understanding'"
                class="compact-answer-compare"
              >
                <view>
                  <text>你的答案</text>
                  <b><math-text :text="answerReveal.student_answer" inline /></b>
                </view>
                <i />
                <view>
                  <text>正确答案</text>
                  <b><math-text :text="answerReveal.correct_answer" inline /></b>
                </view>
              </view>
              <view v-if="!activity.teaching || activity.attempt > 1" class="activity-meta">
                <math-text v-if="!activity.teaching" :text="activity.title" inline />
                <text v-if="activity.attempt > 1">第 {{ activity.attempt }} 次作答</text>
              </view>

              <view
                v-if="activity.visual?.type === 'cube_net'"
                class="cube-net"
                aria-label="正方体展开图"
              >
                <view
                  v-for="cell in activity.visual.cells"
                  :key="`${cell.x}-${cell.y}`"
                  class="cube-cell"
                  :style="{ left: `${cell.x * 25}%`, top: `${cell.y * 33.333}%` }"
                >
                  <math-text :text="cell.label" inline />
                </view>
              </view>
              <image
                v-else-if="showQuestionFigure"
                class="question-figure"
                :src="session.question.figure_url"
                mode="widthFix"
                @error="figureFailed = true"
              />

              <view v-if="activity.teaching" class="teaching-note">
                <view class="teaching-heading">
                  <math-text :text="activity.teaching_title || activity.title" inline />
                  <button
                    tabindex="0"
                    role="button"
                    v-if="canCollapseTeaching"
                    @click="teachingExpanded = !teachingExpanded"
                    @keydown.enter.prevent="teachingExpanded = !teachingExpanded"
                    @keydown.space.prevent
                    @keyup.space.prevent="teachingExpanded = !teachingExpanded"
                  >
                    {{ teachingExpanded ? '收起' : '展开全部' }}
                  </button>
                </view>
                <view
                  class="teaching-body"
                  :class="{ collapsed: canCollapseTeaching && !teachingExpanded }"
                >
                  <math-text class="teaching-content" :text="activity.teaching" />
                  <view v-if="canCollapseTeaching && !teachingExpanded" class="teaching-fade" />
                </view>
              </view>
              <view v-if="activity.feedback" class="feedback" :class="feedbackTone">
                <view class="feedback-heading">
                  <b>{{ activity.attempt > 1 ? '上次作答提示' : '小智老师提示' }}</b>
                  <button
                    tabindex="0"
                    role="button"
                    v-if="canCollapseFeedback"
                    @click="feedbackExpanded = !feedbackExpanded"
                    @keydown.enter.prevent="feedbackExpanded = !feedbackExpanded"
                    @keydown.space.prevent
                    @keyup.space.prevent="feedbackExpanded = !feedbackExpanded"
                  >
                    {{ feedbackExpanded ? '收起' : '展开全部' }}
                  </button>
                </view>
                <view
                  class="feedback-body"
                  :class="{ collapsed: canCollapseFeedback && !feedbackExpanded }"
                >
                  <math-text :text="activity.feedback" />
                  <view v-if="canCollapseFeedback && !feedbackExpanded" class="feedback-fade" />
                </view>
              </view>

              <math-text class="activity-question" :text="activity.question" inline />

              <view v-if="grading" class="grading-state" aria-live="polite">
                <view class="grading-spinner" />
                <b>正在检查答案和过程</b>
                <text>小智老师正在核对关键步骤，请稍候…</text>
              </view>

              <view v-else-if="isChoice" class="option-list">
                <button
                  :aria-disabled="busy"
                  :tabindex="busy ? -1 : 0"
                  role="button"
                  v-for="option in activity.options"
                  :key="option.value"
                  class="option-button"
                  :class="{ selected: selectedOptions.includes(option.value) }"
                  :disabled="busy"
                  @click="chooseOption(option.value)"
                  @keydown.enter.prevent="!busy && chooseOption(option.value)"
                  @keydown.space.prevent
                  @keyup.space.prevent="!busy && chooseOption(option.value)"
                >
                  <i>
                    <uni-icons
                      aria-hidden="true"
                      v-if="selectedOptions.includes(option.value)"
                      type="checkmarkempty"
                      size="17"
                      color="#FFFFFF"
                    />
                  </i>
                  <math-text class="option-label" :text="option.label" inline />
                </button>
                <button
                  :aria-disabled="busy"
                  :tabindex="busy ? -1 : 0"
                  role="button"
                  v-if="
                    session.stage === 'understanding' &&
                    !String(activity.id).includes('confirmation')
                  "
                  class="unknown-button"
                  :disabled="busy"
                  @click="submitUnknown"
                  @keydown.enter.prevent="!busy && submitUnknown"
                  @keydown.space.prevent
                  @keyup.space.prevent="!busy && submitUnknown"
                >
                  我还不知道
                </button>
                <button
                  :aria-disabled="busy || !selectedOptions.length"
                  :tabindex="busy || !selectedOptions.length ? -1 : 0"
                  role="button"
                  v-if="activity.type === 'multiple_choice'"
                  class="primary-btn"
                  :disabled="busy || !selectedOptions.length"
                  @click="submitSelected"
                  @keydown.enter.prevent="!(busy || !selectedOptions.length) && submitSelected"
                  @keydown.space.prevent
                  @keyup.space.prevent="!(busy || !selectedOptions.length) && submitSelected"
                >
                  提交选择
                </button>
              </view>

              <view v-else class="answer-area">
                <view v-if="activity.type === 'teach_back'" class="speaking-help">
                  <math-text
                    class="starter"
                    :text="activity.sentence_starter || '我会先看……'"
                    inline
                  />
                  <view class="keyword-row">
                    <button
                      tabindex="0"
                      role="button"
                      v-for="keyword in activity.keywords || []"
                      :key="keyword"
                      @click="appendKeyword(keyword)"
                      @keydown.enter.prevent="appendKeyword(keyword)"
                      @keydown.space.prevent
                      @keyup.space.prevent="appendKeyword(keyword)"
                    >
                      <math-text :text="keyword" inline />
                    </button>
                  </view>
                </view>
                <view v-if="isFinalTeachAttempt" class="continue-note">
                  <view>
                    <b>还是讲不清也没关系</b>
                    <text>小智老师会记下这次需要帮助，然后用一道简单题继续带你理解。</text>
                  </view>
                  <button
                    :aria-disabled="busy"
                    :tabindex="busy ? -1 : 0"
                    role="button"
                    :disabled="busy"
                    @click="skipTeachBack"
                    @keydown.enter.prevent="!busy && skipTeachBack"
                    @keydown.space.prevent
                    @keyup.space.prevent="!busy && skipTeachBack"
                  >
                    先继续练习
                  </button>
                </view>
                <input
                  v-if="isShortInput && !isCalculation"
                  v-model="activityAnswer"
                  aria-label="你的回答"
                  class="short-answer-input"
                  maxlength="160"
                  :placeholder="answerPlaceholder"
                  confirm-type="done"
                />
                <written-answer
                  v-else
                  ref="writtenAnswer"
                  v-model="activityAnswer"
                  v-model:working="activityWorking"
                  :placeholder="answerPlaceholder"
                  :show-working="isCalculation"
                  :allow-handwriting="canUploadHandwriting"
                  :final-answer-only="isCalculation"
                  upload-url="/answers/handwriting"
                  :upload-data="handwritingContext"
                  @handwriting-change="onHandwritingChange"
                  @uploading-change="uploadingHandwriting = $event"
                />
                <button
                  :aria-disabled="busy"
                  :tabindex="busy ? -1 : 0"
                  role="button"
                  v-if="canAskWritingHelp"
                  class="writing-help-button"
                  :disabled="busy"
                  @click="submitUnknown"
                  @keydown.enter.prevent="!busy && submitUnknown"
                  @keydown.space.prevent
                  @keyup.space.prevent="!busy && submitUnknown"
                >
                  我不会写，请教我
                </button>
                <button
                  :aria-disabled="busy || uploadingHandwriting || !activityAnswer.trim()"
                  :tabindex="busy || uploadingHandwriting || !activityAnswer.trim() ? -1 : 0"
                  role="button"
                  class="primary-btn"
                  :disabled="busy || uploadingHandwriting || !activityAnswer.trim()"
                  @click="submitTextAnswer"
                  @keydown.enter.prevent="
                    !(busy || uploadingHandwriting || !activityAnswer.trim()) && submitTextAnswer
                  "
                  @keydown.space.prevent
                  @keyup.space.prevent="
                    !(busy || uploadingHandwriting || !activityAnswer.trim()) && submitTextAnswer
                  "
                >
                  {{ activity.type === 'teach_back' ? '讲完了' : '提交答案' }}
                </button>
              </view>
            </template>
          </view>

          <view v-else-if="understandingPassed" class="success-card">
            <view class="success-check">
              <uni-icons
                aria-hidden="true"
                type="checkmarkempty"
                size="25"
                color="var(--color-primary)"
              />
            </view>
            <b>已经抓住这个关键点</b>
            <text>接下来只用一句自己的话说清楚，不需要复述完整答案。</text>
            <button
              :aria-disabled="busy"
              :tabindex="busy ? -1 : 0"
              role="button"
              class="primary-btn"
              :disabled="busy"
              @click="advanceToTeachBack"
              @keydown.enter.prevent="!busy && advanceToTeachBack"
              @keydown.space.prevent
              @keyup.space.prevent="!busy && advanceToTeachBack"
            >
              继续：用自己的话说一遍
            </button>
          </view>

          <view v-else-if="session.stage === 'finished'" class="success-card finish-card">
            <view class="success-check">
              <uni-icons
                aria-hidden="true"
                type="checkmarkempty"
                size="25"
                color="var(--color-primary)"
              />
            </view>
            <b>
              {{ session.state?.transfer_insufficient ? '本轮学习已完成' : '本次学习完成' }}
            </b>
            <math-text
              :text="session.completion_summary || '掌握状态和后续复习已经更新。'"
              inline
            />
            <text v-if="session.assisted" class="assisted-note">
              这次有小智老师帮助，之后会更早安排复习。
            </text>
            <button
              tabindex="0"
              role="button"
              class="primary-btn"
              @click="uni.reLaunch({ url: '/pages/index/index' })"
              @keydown.enter.prevent="uni.reLaunch({ url: '/pages/index/index' })"
              @keydown.space.prevent
              @keyup.space.prevent="uni.reLaunch({ url: '/pages/index/index' })"
            >
              完成
            </button>
          </view>

          <view v-if="session.turns?.length" class="history-section">
            <button
              tabindex="0"
              role="button"
              class="history-toggle"
              @click="historyOpen = !historyOpen"
              @keydown.enter.prevent="historyOpen = !historyOpen"
              @keydown.space.prevent
              @keyup.space.prevent="historyOpen = !historyOpen"
            >
              <text>{{ historyOpen ? '收起之前的对话' : '查看之前的对话' }}</text>
              <i :class="{ open: historyOpen }" />
            </button>
            <view v-if="historyOpen" class="history-list">
              <view
                v-for="turn in session.turns"
                :key="turn.id"
                :class="['history-turn', turn.role]"
              >
                <text>{{ turn.role === 'assistant' ? '小智老师' : '我' }}</text>
                <view>
                  <math-text
                    :text="
                      turn.role === 'assistant' ? learningFeedback(turn.content) : turn.content
                    "
                    inline
                  />
                  <view
                    v-if="
                      turn.role === 'assistant' && turn.metadata_json?.knowledge_sources?.length
                    "
                    class="knowledge-sources"
                  >
                    <button
                      role="button"
                      class="source-toggle"
                      @click="sourceOpen[turn.id] = !sourceOpen[turn.id]"
                      tabindex="0"
                      :aria-expanded="Boolean(sourceOpen[turn.id])"
                      @keydown.enter.prevent="sourceOpen[turn.id] = !sourceOpen[turn.id]"
                      @keydown.space.prevent
                      @keyup.space.prevent="sourceOpen[turn.id] = !sourceOpen[turn.id]"
                    >
                      参考知识
                      <uni-icons
                        aria-hidden="true"
                        :type="sourceOpen[turn.id] ? 'top' : 'bottom'"
                        size="14"
                      />
                    </button>
                    <template v-if="sourceOpen[turn.id]">
                      <button
                        v-for="source in turn.metadata_json.knowledge_sources"
                        :key="source.code"
                        role="button"
                        class="source-link"
                        tabindex="0"
                        @keydown.enter.prevent="
                          go('/pages/library/library?code=' + encodeURIComponent(source.code))
                        "
                        @keydown.space.prevent
                        @keyup.space.prevent="
                          go('/pages/library/library?code=' + encodeURIComponent(source.code))
                        "
                        @click="
                          go('/pages/library/library?code=' + encodeURIComponent(source.code))
                        "
                      >
                        {{ source.name }}
                        <text v-if="source.role === 'prerequisite'">先修</text>
                        <uni-icons aria-hidden="true" type="right" size="14" />
                      </button>
                    </template>
                  </view>
                </view>
              </view>
            </view>
          </view>
          <view class="bottom-space" />
        </view>
      </scroll-view>

      <view class="helper-bar">
        <view class="helper-bar-inner">
          <template v-if="askOpen">
            <input
              v-model="askInput"
              focus
              placeholder="问一个当前没弄懂的地方"
              confirm-type="send"
              @confirm="sendQuestion"
            />
            <button
              :aria-disabled="busy || !askInput.trim()"
              :tabindex="busy || !askInput.trim() ? -1 : 0"
              role="button"
              class="helper-text"
              :disabled="busy || !askInput.trim()"
              @click="sendQuestion"
              @keydown.enter.prevent="!(busy || !askInput.trim()) && sendQuestion"
              @keydown.space.prevent
              @keyup.space.prevent="!(busy || !askInput.trim()) && sendQuestion"
            >
              发送
            </button>
            <button
              tabindex="0"
              role="button"
              class="helper-text quiet"
              @click="askOpen = false"
              @keydown.enter.prevent="askOpen = false"
              @keydown.space.prevent
              @keyup.space.prevent="askOpen = false"
            >
              取消
            </button>
          </template>
          <template v-else>
            <button
              tabindex="0"
              role="button"
              @click="askOpen = true"
              @keydown.enter.prevent="askOpen = true"
              @keydown.space.prevent
              @keyup.space.prevent="askOpen = true"
            >
              向 AI 提问
            </button>
            <button
              :aria-disabled="busy"
              :tabindex="busy ? -1 : 0"
              role="button"
              v-if="session.stage !== 'finished' && session.visualization_available"
              :disabled="busy"
              @click="uni.navigateTo({ url: `/pages/visualization/visualization?id=${id}` })"
              @keydown.enter.prevent="
                !busy && uni.navigateTo({ url: `/pages/visualization/visualization?id=${id}` })
              "
              @keydown.space.prevent
              @keyup.space.prevent="
                !busy && uni.navigateTo({ url: `/pages/visualization/visualization?id=${id}` })
              "
            >
              互动演示
            </button>
          </template>
        </view>
      </view>
    </template>
  </view>
</template>

<script setup>
import { learningFeedback } from '@/utils/learning-feedback.js'
import MathText from '@/components/math-text/math-text.vue'
import WrittenAnswer from '@/components/written-answer/written-answer.vue'

import { computed, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { getData, postData } from '@/api/index.js'
import { go } from '@/utils/navigation.js'

const id = ref('')
const session = ref(null)
const busy = ref(false)
const grading = ref(false)
const error = ref(false)
const figureFailed = ref(false)
const selectedOptions = ref([])
const activityAnswer = ref('')
const activityWorking = ref('')
const sourceOpen = ref({})
const historyOpen = ref(false)
const questionOpen = ref(false)
const planOpen = ref(false)
const askOpen = ref(false)
const askInput = ref('')
const writtenAnswer = ref(null)
const handwritingImage = ref('')
const handwritingRecognition = ref(null)
const uploadingHandwriting = ref(false)
const teachingExpanded = ref(false)
const feedbackExpanded = ref(false)
const stages = ['理解', '讲清', '练习', '迁移']

const activity = computed(() => {
  const value = session.value?.activity
  return value ? { ...value, feedback: learningFeedback(value.feedback) } : null
})
const answerReveal = computed(() => session.value?.answer_reveal || {})
const teachingMode = computed(() => session.value?.teaching_policy?.mode || 'full')
const isCompressed = computed(() => teachingMode.value === 'compressed')
const isAnswerReveal = computed(() => activity.value?.type === 'explanation')
const understandingPassed = computed(
  () => session.value?.stage === 'understanding' && session.value?.stage_status === 'passed',
)
const isChoice = computed(() => ['single_choice', 'multiple_choice'].includes(activity.value?.type))
const showQuestionFigure = computed(
  () =>
    !isCompressed.value &&
    session.value?.stage === 'understanding' &&
    session.value?.question?.figure_url &&
    !figureFailed.value,
)
const stageIndex = computed(
  () =>
    ({ understanding: 0, teach_back: 1, near_transfer: 2, far_transfer: 3, finished: 4 })[
      session.value?.stage
    ] ?? 0,
)
const visibleStages = computed(() => (isCompressed.value ? ['讲解', '练一道', '完成'] : stages))
const visibleStageIndex = computed(() => {
  if (!isCompressed.value) return stageIndex.value
  if (session.value?.stage === 'finished') return 2
  if (['near_transfer', 'far_transfer'].includes(session.value?.stage)) return 1
  return 0
})
const canRewind = computed(() =>
  ['teach_back', 'near_transfer', 'far_transfer'].includes(session.value?.stage),
)
const inputMode = computed(
  () => activity.value?.input_mode || session.value?.teaching_policy?.question_type || '',
)
const isShortInput = computed(
  () => activity.value?.type === 'short_answer' || inputMode.value === 'fill_blank',
)
const isCalculation = computed(() => inputMode.value === 'calculation')
const canUploadHandwriting = computed(
  () =>
    !isChoice.value &&
    activity.value?.type !== 'teach_back' &&
    (isCalculation.value || (activity.value?.type === 'variant' && !isShortInput.value)),
)
const handwritingContext = computed(() => ({
  context_type: 'tutor',
  context_id: id.value,
  activity_id: activity.value?.id || '',
}))
const canAskWritingHelp = computed(
  () => activity.value?.type === 'variant' && !isChoice.value && !isShortInput.value,
)
const canCollapseTeaching = computed(
  () =>
    String(activity.value?.teaching || '').length > 150 ||
    String(activity.value?.teaching || '').split('\n').length > 4,
)
const canCollapseFeedback = computed(
  () =>
    String(activity.value?.feedback || '').length > 60 ||
    String(activity.value?.feedback || '').split('\n').length > 2,
)
const introText = computed(() => {
  if (isAnswerReveal.value) return '先看答案，再只修正这一个易错点。'
  if (session.value?.stage === 'understanding') return '我们先只解决一个小问题。'
  if (session.value?.stage === 'teach_back') return '不用讲完整解法，用一句话说清关键判断。'
  if (session.value?.stage === 'near_transfer') return '现在做一道很像的题，把刚学会的方法用起来。'
  return '最后换一种问法，看看你能不能认出同一个关键点。'
})
const feedbackTone = computed(() => {
  const value = activity.value?.feedback || ''
  if (/答对|继续|抓住|完成/.test(value)) return 'success'
  return 'warning'
})
const answerPlaceholder = computed(() => {
  if (activity.value?.type === 'teach_back') return activity.value?.sentence_starter || '我会先看……'
  if (isCalculation.value) return '写下最终答案'
  if (isShortInput.value) return '填写答案'
  return '写下你的证明或回答'
})
const isFinalTeachAttempt = computed(
  () =>
    activity.value?.type === 'teach_back' &&
    Number(activity.value?.attempt) >= Number(activity.value?.max_attempts || 2),
)

let activityStartedAt = Date.now()
function resetActivityInput() {
  activityStartedAt = Date.now()
  selectedOptions.value = []
  activityAnswer.value = ''
  activityWorking.value = ''
  writtenAnswer.value?.reset()
  handwritingImage.value = ''
  handwritingRecognition.value = null
  teachingExpanded.value = false
  feedbackExpanded.value = false
}

async function load(preserveInput = false) {
  if (!id.value) return
  try {
    const previousActivity = activity.value?.id
    session.value = await getData(`/tutor/sessions/${id.value}`)
    error.value = false
    if (!preserveInput || previousActivity !== activity.value?.id) resetActivityInput()
  } catch {
    error.value = true
  }
}

async function applyActivityAnswer(answer, unknown = false, working = '') {
  if (!activity.value || busy.value) return
  busy.value = true
  grading.value = true
  try {
    session.value = await postData(
      `/tutor/sessions/${id.value}/activity/answer`,
      {
        activity_id: activity.value.id,
        answer,
        unknown,
        working,
        handwriting_image_url: handwritingImage.value,
        handwriting_recognition: handwritingRecognition.value,
        elapsed_seconds: Math.max(1, Math.round((Date.now() - activityStartedAt) / 1000)),
      },
      { silent: true },
    )
    resetActivityInput()
  } catch (requestError) {
    if (requestError?.statusCode === 409) {
      await load()
      uni.showToast({ title: '练习已更新，请继续作答', icon: 'none' })
    } else {
      uni.showToast({ title: requestError?.message || '提交没有成功，请稍后重试', icon: 'none' })
    }
  } finally {
    grading.value = false
    busy.value = false
  }
}

function chooseOption(value) {
  if (activity.value?.type === 'multiple_choice') {
    selectedOptions.value = selectedOptions.value.includes(value)
      ? selectedOptions.value.filter((item) => item !== value)
      : [...selectedOptions.value, value]
    return
  }
  selectedOptions.value = [value]
  applyActivityAnswer(value)
}

function submitSelected() {
  applyActivityAnswer(selectedOptions.value)
}
function submitUnknown() {
  applyActivityAnswer('__unknown__', true)
}
function submitTextAnswer() {
  applyActivityAnswer(activityAnswer.value, false, activityWorking.value)
}
function onHandwritingChange(value) {
  handwritingImage.value = value.image_url || ''
  handwritingRecognition.value = value.recognition || null
}
function acknowledgeBrief(action) {
  applyActivityAnswer(action)
}
function skipTeachBack() {
  askOpen.value = false
  applyActivityAnswer('我现在还讲不清这个关键点')
}
function appendKeyword(keyword) {
  const value = String(keyword || '').trim()
  if (!value || activityAnswer.value.includes(value)) return
  activityAnswer.value = `${activityAnswer.value}${activityAnswer.value ? '，' : '我会先看'}${value}`
}

async function advanceToTeachBack() {
  if (busy.value) return
  busy.value = true
  try {
    await postData(`/tutor/sessions/${id.value}/advance`, { target_stage: 'teach_back' })
    await load()
  } finally {
    busy.value = false
  }
}

async function rewindStage() {
  if (!canRewind.value || busy.value) return
  busy.value = true
  askOpen.value = false
  try {
    session.value = await postData(`/tutor/sessions/${id.value}/rewind`, {})
    resetActivityInput()
  } finally {
    busy.value = false
  }
}

function rewindFromStage(index) {
  if (canRewind.value && index === visibleStageIndex.value - 1) rewindStage()
}

async function sendQuestion() {
  if (!askInput.value.trim() || busy.value) return
  busy.value = true
  try {
    await postData(`/tutor/sessions/${id.value}/turns`, { message: askInput.value.trim() })
    askInput.value = ''
    askOpen.value = false
    historyOpen.value = true
    await load(true)
  } finally {
    busy.value = false
  }
}

onLoad((query) => {
  id.value = query.id
  if (query.ask) {
    askInput.value = String(query.ask).slice(0, 1000)
    askOpen.value = true
  }
  load()
})
</script>

<style scoped lang="scss">
.tutor-page {
  height: 100vh;
  height: 100dvh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--color-bg);
}
.context-action {
  min-height: 48px;
  padding: 12px 8px;
  margin: 0;
  background: transparent;
  color: var(--color-primary);
  font-size: 14px;
}
.question-context {
  padding: 16px;
  margin-bottom: 16px;
  border: 1px solid var(--color-border);
  border-radius: 12px;
  background: var(--color-surface);
}
.stage-strip {
  height: 41px;
  flex: none;
  display: flex;
  align-items: center;
  padding: 0 21px;
  background: #fff;
  border-bottom: 0.5px solid var(--color-border);
}
.stage-strip > view {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  color: var(--color-text-tertiary);
  font-size: 12px;
  position: relative;
}
.stage-strip > view:not(:last-child)::after {
  content: '';
  position: absolute;
  left: 76%;
  right: -24%;
  top: 9px;
  height: 0.5px;
  background: var(--color-border);
}
.stage-strip i {
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: #f2f4f7;
  font-style: normal;
  font-size: 9.5px;
}
.stage-strip .active {
  color: var(--color-primary-hover);
  font-weight: 600;
}
.stage-strip .active i {
  background: var(--color-surface-subtle);
  color: var(--color-primary);
}
.stage-strip .done {
  color: var(--color-primary);
}
.stage-strip .done i {
  background: var(--color-surface-subtle);
  color: var(--color-primary);
}
.stage-strip .backable {
  cursor: pointer;
}
.stage-strip .backable text {
  text-decoration: underline;
  text-underline-offset: 2.5px;
}
.stage-strip .backable:active {
  opacity: 0.65;
}
.task-scroll {
  height: 0;
  flex: 1;
  min-height: 0;
}
.task-content {
  padding: 14px 14px 0;
}
.rewind-button {
  min-height: 31px;
  margin: 0 0 7px;
  padding: 0 2px;
  display: flex;
  align-items: center;
  gap: 5px;
  background: transparent;
  color: var(--color-text-secondary);
  font-size: 12px;
  text-align: left;
}
.rewind-button i {
  width: 7px;
  height: 7px;
  border-left: 1px solid currentColor;
  border-bottom: 1px solid currentColor;
  transform: rotate(45deg);
}
.teacher-intro {
  padding: 2px 2px 10px;
}
.teacher-intro text,
.teacher-intro b {
  display: block;
}
.teacher-intro text {
  color: var(--color-text-secondary);
  font-size: 12px;
  font-weight: 600;
}
.teacher-intro b {
  margin-top: 4px;
  font-size: 15px;
  line-height: 1.55;
}
.activity-card,
.success-card {
  padding: 16px;
  background: #fff;
  border-radius: var(--radius-card);
}
.answer-brief-heading {
  padding-bottom: 11px;
  border-bottom: 0.5px solid var(--color-border);
}
.answer-brief-heading > .math-text,
.answer-brief-heading b {
  display: block;
}
.answer-brief-heading > .math-text {
  color: var(--color-text-secondary);
  font-size: 12px;
}
.answer-brief-heading b {
  margin-top: 3px;
  font-size: 15.5px;
  line-height: 1.4;
}
.answer-compare {
  display: grid;
  grid-template-columns: 1fr 1fr;
  margin: 12px 0;
  border: 0.5px solid var(--color-border);
  border-radius: 4px;
  overflow: hidden;
}
.answer-compare > view {
  padding: 10px 11px;
}
.answer-compare > view + view {
  border-left: 0.5px solid var(--color-border);
}
.answer-compare text,
.answer-compare b {
  display: block;
}
.answer-compare text {
  font-size: 12px;
  color: var(--color-text-secondary);
}
.answer-compare b {
  margin-top: 4px;
  font-size: 19px;
  line-height: 1;
}
.student-answer {
  color: var(--color-error);
}
.correct-answer {
  color: var(--color-primary);
}
.why-block {
  padding-top: 2px;
}
.why-block > b {
  display: block;
  font-size: 14px;
}
.why-block > .math-text {
  display: block;
  margin-top: 4.5px;
  color: var(--color-text-secondary);
  font-size: 12px;
  line-height: 1.55;
}
.option-explanations {
  margin-top: 9px;
  border-top: 0.5px solid var(--color-border);
}
.option-explanations > view {
  min-height: 33px;
  display: flex;
  align-items: center;
  gap: 7px;
  border-bottom: 0.5px solid var(--color-border);
}
.option-explanations i {
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
  border: 0.5px solid var(--color-border);
  border-radius: 50%;
  font-style: normal;
  font-size: 12px;
  font-weight: 650;
}
.option-explanations .math-text {
  flex: 1;
  color: var(--color-text-secondary);
  font-size: 12px;
  line-height: 1.45;
}
.option-explanations b {
  color: var(--color-primary);
  font-size: 12px;
}
.option-explanations > view.correct i {
  border-color: var(--color-primary);
  color: var(--color-primary);
}
.brief-actions {
  margin-top: 13px;
}
.brief-actions .primary-btn {
  margin-top: 0;
}
.secondary-btn {
  width: 100%;
  min-height: 44px;
  margin-top: 6px;
  border: 0.5px solid var(--color-border);
  border-radius: 8px;
  background: #fff;
  color: var(--color-text-secondary);
  font-size: 12px;
}
.compact-answer-compare {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 11px;
  padding: 8px 9px;
  border-bottom: 1px solid var(--color-border);
  padding-bottom: 12px;
  background: transparent;
}
.compact-answer-compare > view {
  flex: 1;
  color: var(--color-text-secondary);
  font-size: 12px;
}
.compact-answer-compare b {
  display: block;
  margin-top: 2px;
  color: var(--color-text-primary);
  font-size: 14px;
}
.compact-answer-compare > view:last-child b {
  color: var(--color-primary);
}
.compact-answer-compare i {
  width: 0.5px;
  height: 21px;
  background: var(--color-border);
}
.activity-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 11px;
}
.activity-meta > .math-text:first-child {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-primary-hover);
}
.activity-meta text:last-child {
  font-size: 12px;
  color: var(--color-text-tertiary);
}
.question-figure {
  display: block;
  width: 100%;
  max-height: 180px;
  margin: 0 0 11px;
  border: 0.5px solid var(--color-border);
  border-radius: 4px;
  background: #fff;
}
.cube-net {
  position: relative;
  width: 100%;
  height: 135px;
  margin: 0 0 12px;
  background: var(--color-surface-subtle);
  border-radius: 4px;
}
.cube-cell {
  position: absolute;
  width: 25%;
  height: 33.333%;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #667085;
  background: #fff;
  font-size: 14.5px;
  font-weight: 600;
}
.teaching-note {
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  overflow: hidden;
  padding: 8px 0;
  margin-bottom: 12px;
  border-bottom: 1px solid var(--color-border);
  background: transparent;
}
.teaching-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.teaching-heading > .math-text {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
}
.teaching-heading button {
  flex: none;
  min-height: 44px;
  margin: 0;
  padding: 8px 10px;
  border: 0.5px solid var(--color-border);
  border-radius: 5px;
  background: #fff;
  color: var(--color-text-secondary);
  font-size: 12px;
}
.teaching-body {
  position: relative;
  max-width: 100%;
  min-width: 0;
}
.teaching-body.collapsed {
  max-height: 150px;
  overflow: hidden;
}
.teaching-content {
  max-width: 100%;
  margin-top: 3px;
  font-size: 13px;
  line-height: 1.65;
  font-weight: 500;
  color: var(--color-text-secondary);
}
.teaching-fade {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 36px;
  background: var(--color-surface-subtle);
  height: 4px;
  border-top: 0.5px dashed var(--color-border);
}
.feedback {
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  overflow: hidden;
  padding: 9px 10px;
  margin-bottom: 9px;
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.55;
}
.feedback-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 7px;
}
.feedback-heading > b {
  display: block;
  font-size: 12px;
}
.feedback-heading button {
  flex: none;
  min-height: 24px;
  margin: 0;
  padding: 0 6.5px;
  border: 0.5px solid var(--color-border);
  border-radius: 4.5px;
  background: #fff;
  color: var(--color-text-secondary);
  font-size: 9.5px;
}
.feedback-body {
  position: relative;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  margin-top: 2.5px;
  overflow-wrap: anywhere;
}
.feedback-body.collapsed {
  max-height: 75px;
  overflow: hidden;
}
.feedback-fade {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 30px;
  background: var(--color-surface-subtle);
  height: 4px;
  border-top: 0.5px dashed var(--color-border);
}
.feedback.warning {
  background: var(--color-surface-subtle);
  color: var(--color-text-secondary);
}
.feedback.success {
  background: var(--color-surface-subtle);
  color: var(--color-text-primary);
}
.activity-question {
  display: block;
  font-size: 16.5px;
  font-weight: 650;
  line-height: 1.65;
  color: var(--color-text-primary);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.grading-state {
  min-height: 150px;
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 19px 12px;
  border: 0.5px solid var(--color-primary-border);
  border-radius: 4px;
  background: var(--color-surface-subtle);
  text-align: center;
}
.grading-spinner {
  width: 27px;
  height: 27px;
  border: 3px solid #d8e5ff;
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: grading-spin 0.8s linear infinite;
}
.grading-state b {
  margin-top: 11px;
  font-size: 14px;
  color: var(--color-text-primary);
}
.grading-state text {
  margin-top: 4px;
  font-size: 12px;
  color: var(--color-text-secondary);
}
@keyframes grading-spin {
  to {
    transform: rotate(360deg);
  }
}
.option-list {
  display: flex;
  flex-direction: column;
  gap: 7px;
  margin-top: 14px;
}
.option-button,
.unknown-button {
  min-height: 44px;
  margin: 0;
  display: flex;
  align-items: center;
  padding: 7.5px 10px;
  border: 0.5px solid var(--color-border);
  border-radius: 8px;
  background: #fff;
  color: var(--color-text-primary);
  font-size: 14px;
  text-align: left;
}
.option-button i {
  width: 21px;
  height: 21px;
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 8px;
  border: 1px solid #cdd3dc;
  border-radius: 50%;
  font-style: normal;
  color: #fff;
  font-size: 12px;
}
.option-label {
  flex: 1;
  min-width: 0;
  line-height: 1.55;
}
.option-button.selected {
  border-color: var(--color-primary-border);
  background: var(--color-surface-subtle);
}
.option-button.selected i {
  border-color: var(--color-primary);
  background: var(--color-primary);
}
.unknown-button {
  justify-content: center;
  color: var(--color-text-secondary);
  background: var(--color-surface-subtle);
}
.answer-area {
  margin-top: 12px;
}
.speaking-help {
  margin-bottom: 9px;
}
.starter {
  display: block;
  color: var(--color-text-secondary);
  font-size: 13px;
}
.keyword-row {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 6px;
}
.keyword-row button {
  min-height: 29px;
  margin: 0;
  padding: 3.5px 8px;
  border: 0.5px solid var(--color-border);
  border-radius: 4px;
  background: #fff;
  color: #475467;
  font-size: 12px;
}
.keyword-row button:active {
  border-color: var(--color-primary-border);
  background: var(--color-surface-subtle);
  color: var(--color-primary-hover);
}
.continue-note {
  display: flex;
  align-items: center;
  gap: 9px;
  margin: 0 0 10px;
  padding: 10px;
  border: 0.5px solid var(--color-primary-border);
  border-radius: 4px;
  background: var(--color-surface-subtle);
}
.continue-note > view {
  flex: 1;
  min-width: 0;
}
.continue-note b,
.continue-note text {
  display: block;
}
.continue-note b {
  font-size: 12px;
}
.continue-note text {
  margin-top: 2px;
  color: var(--color-text-secondary);
  font-size: 12px;
  line-height: 1.5;
}
.continue-note button {
  flex: none;
  min-height: 33px;
  margin: 0;
  padding: 0 9px;
  border-radius: 6px;
  background: var(--color-primary);
  color: #fff;
  font-size: 12px;
}
.short-answer-input {
  width: 100%;
  height: 41px;
  padding: 0 10px;
  border: 0.5px solid var(--color-border);
  border-radius: 4px;
  background: var(--color-surface-subtle);
  font-size: 14px;
}
.writing-help-button {
  width: 100%;
  min-height: 36px;
  margin: 8px 0 0;
  border: 0.5px solid var(--color-primary-border);
  border-radius: 4px;
  background: #fff;
  color: var(--color-primary-hover);
  font-size: 12px;
}
.primary-btn {
  height: 43px;
  margin-top: 11px;
  border-radius: 4px;
  font-size: 14px;
}
.success-card {
  text-align: left;
  padding-top: 16px;
}
.success-check {
  width: 32px;
  height: 32px;
  margin: 0 0 9px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--color-surface-subtle);
  color: var(--color-primary);
  font-size: 17px;
  font-weight: 700;
}
.success-card b,
.success-card > text,
.success-card > .math-text {
  display: block;
}
.success-card b {
  font-size: 16px;
}
.success-card > text,
.success-card > .math-text {
  margin-top: 5px;
  color: var(--color-text-secondary);
  font-size: 12px;
  line-height: 1.65;
}
.success-card .assisted-note {
  color: var(--color-text-secondary);
}
.history-section {
  margin-top: 11px;
}
.history-toggle {
  width: 100%;
  min-height: 36px;
  margin: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 2px;
  background: transparent;
  color: var(--color-text-secondary);
  font-size: 12px;
  text-align: left;
}
.history-toggle i {
  width: 6.5px;
  height: 6.5px;
  border-right: 1px solid var(--color-text-tertiary);
  border-bottom: 1px solid var(--color-text-tertiary);
  transform: rotate(45deg);
  transition: transform 0.2s;
}
.history-toggle i.open {
  transform: rotate(225deg);
}
.history-list {
  padding: 9px 0;
  border-top: 0.5px solid var(--color-border);
}
.history-turn {
  margin-bottom: 9px;
}
.history-turn > text {
  display: block;
  margin-bottom: 2.5px;
  color: var(--color-text-tertiary);
  font-size: 12px;
}
.history-turn > view {
  padding: 8px 9px;
  border: 0.5px solid var(--color-border);
  border-radius: 4px;
  background: #fff;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
}
.history-turn.user > view {
  background: var(--color-surface-subtle);
  border-color: transparent;
}
.bottom-space {
  height: 67px;
}
.helper-bar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 50;
  min-height: 52px;
  padding: 7px 14px calc(7px + env(safe-area-inset-bottom));
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 9px;
  border-top: 0.5px solid var(--color-border);
  background: rgba(255, 255, 255, 0.98);
}
.helper-bar-inner > button {
  flex: 1;
  min-height: 44px;
  margin: 0;
  border: 0.5px solid var(--color-border);
  border-radius: 8px;
  background: #fff;
  color: #475467;
  font-size: 13px;
}
.helper-bar input {
  flex: 1;
  height: 44px;
  padding: 0 9px;
  border: 0.5px solid var(--color-border);
  border-radius: 4px;
  background: var(--color-surface-subtle);
  font-size: 12px;
}
.helper-bar .helper-text {
  flex: none;
  width: auto;
  padding: 0 5px;
  border: 0;
  color: var(--color-primary-hover);
}
.helper-bar .helper-text.quiet {
  color: var(--color-text-secondary);
}
.helper-bar-inner {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 9px;
  width: 100%;
  max-width: 756px;
  margin: 0 auto;
}
@media (min-width: 768px) {
  .helper-bar {
    width: 100%;
    max-width: 960px;
    margin: 0 auto;
    box-sizing: border-box;
    padding-left: 32px;
    padding-right: 32px;
  }
  .tutor-page {
    max-width: 960px;
    margin: 0 auto;
    border-left: 1px solid var(--color-border);
    border-right: 1px solid var(--color-border);
  }
  .task-content {
    max-width: 820px;
    margin: 0 auto;
  }
  .stage-strip {
    padding-left: max(32px, calc((100% - 756px) / 2));
    padding-right: max(32px, calc((100% - 756px) / 2));
  }
}
</style>

<style scoped lang="scss">
.knowledge-sources {
  margin-top: 12px;
  border-top: 1px solid var(--color-border);
}
.source-toggle,
.source-link {
  display: flex;
  align-items: center;
  width: 100%;
  min-height: 44px;
  gap: 8px;
  margin: 0;
  padding: 8px 0;
  text-align: left;
  color: var(--color-primary);
  background: transparent;
  font-size: 13px;
}
.source-link > text {
  color: var(--color-text-secondary);
  font-size: 12px;
}
.source-link .uni-icons {
  margin-left: auto;
}
</style>
