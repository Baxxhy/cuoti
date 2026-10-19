<template>
  <view class="page home-page">
    <view class="home-top">
      <view class="home-top-copy">
        <!-- #ifdef H5 -->
        <component :is="'h1'" class="greeting">今日</component>
        <!-- #endif -->
        <!-- #ifndef H5 -->
        <text class="greeting">今日</text>
        <!-- #endif -->
        <text class="today-copy">
          {{
            new Date().toLocaleDateString('zh-CN', {
              month: 'long',
              day: 'numeric',
              weekday: 'long',
            })
          }}
        </text>
      </view>
      <button
        class="search-action"
        role="button"
        tabindex="0"
        aria-label="搜索错题"
        @click="go('/pages/search/search')"
        @keydown.enter.prevent="go('/pages/search/search')"
        @keydown.space.prevent
        @keyup.space.prevent="go('/pages/search/search')"
      >
        <uni-icons type="search" size="24" color="#55565B" />
      </button>
    </view>

    <view class="page-content home-content">
      <state-panel
        v-if="loading || error"
        :state="error ? 'error' : 'loading'"
        :message="error"
        @retry="load"
      />
      <template v-else-if="data">
        <view class="home-gateways">
          <button
            v-for="entry in studyEntries"
            :key="entry.url"
            :class="['study-gateway', entry.tone]"
            @click="go(entry.url)"
          >
            <uni-icons
              :type="entry.icon"
              size="28"
              :color="entry.tone === 'orange' ? '#a65916' : '#176cbb'"
            />
            <view>
              <text>{{ entry.title }}</text>
            </view>
            <uni-icons
              type="right"
              size="16"
              :color="entry.tone === 'orange' ? '#a65916' : '#176cbb'"
            />
          </button>
        </view>

        <button
          role="button"
          tabindex="0"
          class="home-direction"
          aria-label="选择学习方向"
          @keydown.enter.prevent="go('/pages/preferences/preferences')"
          @keydown.space.prevent
          @keyup.space.prevent="go('/pages/preferences/preferences')"
          @click="go('/pages/preferences/preferences')"
        >
          <text>
            {{
              preferences?.subject
                ? `${preferences.subject} · ${goalLabel} · 约${preferences.minutes}分钟`
                : '选择今天的学习方向'
            }}
          </text>
          <text>
            调整
            <uni-icons type="right" size="15" />
          </text>
        </button>
        <view v-if="partialError" class="home-partial-error" role="status">
          <text>{{ partialError }}</text>
          <button
            role="button"
            tabindex="0"
            class="disclosure-link"
            @click="load"
            @keydown.enter.prevent="load"
            @keydown.space.prevent
            @keyup.space.prevent="load"
          >
            重新读取学习建议
          </button>
        </view>
        <view class="focus-card">
          <view class="focus-symbol" aria-hidden="true">
            <uni-icons
              :type="
                focusKind === 'capture' ? 'camera' : focusKind === 'review' ? 'calendar' : 'wallet'
              "
              size="32"
              color="var(--color-primary)"
            />
          </view>
          <template v-if="focusKind === 'task'">
            <text class="focus-title">
              {{ taskFocus.student_view?.title || '继续解决上次那一步' }}
            </text>
            <button
              class="primary-btn"
              role="button"
              tabindex="0"
              @click="go(`/pages/task/task?id=${taskFocus.id}`)"
              @keydown.enter.prevent="go(`/pages/task/task?id=${taskFocus.id}`)"
            >
              继续这一步
            </button>
          </template>
          <template v-else-if="focusKind === 'continue'">
            <text class="focus-title">{{ data.continue_learning.knowledge_point }}</text>
            <text class="focus-next">下一步：{{ data.continue_learning.next_step }}</text>
            <button
              tabindex="0"
              role="button"
              class="primary-btn"
              @click="go(`/pages/tutor/tutor?id=${data.continue_learning.session_id}`)"
              @keydown.enter.prevent="
                go(`/pages/tutor/tutor?id=${data.continue_learning.session_id}`)
              "
              @keydown.space.prevent
              @keyup.space.prevent="
                go(`/pages/tutor/tutor?id=${data.continue_learning.session_id}`)
              "
            >
              继续学习
            </button>
          </template>
          <template v-else-if="focusKind === 'review'">
            <text class="focus-title">今天有 {{ data.today_reviews }} 道题待复习</text>
            <button
              tabindex="0"
              role="button"
              class="primary-btn"
              @click="go('/pages/review/review')"
              @keydown.enter.prevent="go('/pages/review/review')"
              @keydown.space.prevent
              @keyup.space.prevent="go('/pages/review/review')"
            >
              开始复习
            </button>
          </template>
          <template v-else-if="focusKind === 'assignment'">
            <text class="focus-title">{{ data.teacher_assignment_count }} 项教师任务待完成</text>
            <button
              tabindex="0"
              role="button"
              class="primary-btn"
              @click="go('/pages/assignment/assignment')"
              @keydown.enter.prevent="go('/pages/assignment/assignment')"
              @keydown.space.prevent
              @keyup.space.prevent="go('/pages/assignment/assignment')"
            >
              查看任务
            </button>
          </template>
          <template v-else-if="focusKind === 'repair'">
            <text class="focus-title">先核对：{{ recommendedGroup.label }}</text>
            <text class="focus-next">
              {{ recommendedGroup.subject }} ·
              {{
                recommendedGroup.sources.length > 1
                  ? `${recommendedGroup.sources.length}道题中出现相同诊断线索`
                  : '来自你最近的一道题'
              }}。先回放，再沿路线修复。
            </text>
            <button
              role="button"
              tabindex="0"
              class="primary-btn"
              @keydown.enter.prevent="
                go(`/pages/repair/repair?id=${recommendedGroup.sources[0].id}`)
              "
              @keydown.space.prevent
              @keyup.space.prevent="go(`/pages/repair/repair?id=${recommendedGroup.sources[0].id}`)"
              @click="go(`/pages/repair/repair?id=${recommendedGroup.sources[0].id}`)"
            >
              查看这次修复路线
            </button>
          </template>
          <template v-else-if="focusKind === 'starter'">
            <text class="focus-title">{{ preferences.subject }}</text>
            <button
              role="button"
              tabindex="0"
              class="primary-btn"
              @keydown.enter.prevent="openKnowledge"
              @keydown.space.prevent
              @keyup.space.prevent="openKnowledge"
              @click="openKnowledge"
            >
              选择知识与例题
            </button>
          </template>
          <template v-else>
            <text class="focus-title">录入错题</text>
            <button
              tabindex="0"
              role="button"
              class="primary-btn"
              @click="go('/pages/capture/capture')"
              @keydown.enter.prevent="go('/pages/capture/capture')"
              @keydown.space.prevent
              @keyup.space.prevent="go('/pages/capture/capture')"
            >
              <uni-icons type="camera-filled" size="22" color="var(--color-surface)" />
              <text>拍照或选择图片</text>
            </button>
          </template>
        </view>

        <view class="home-secondary">
          <view v-if="focusKind === 'capture'" class="home-starter">
            <button
              aria-label="知识与例题"
              role="button"
              tabindex="0"
              class="disclosure-link"
              @keydown.enter.prevent="openKnowledge"
              @keydown.space.prevent
              @keyup.space.prevent="openKnowledge"
              @click="openKnowledge"
            >
              <view class="entry-label">
                <uni-icons type="wallet" size="22" color="var(--color-primary)" />
                <text>知识与例题</text>
              </view>
              <uni-icons type="right" size="18" />
            </button>
          </view>

          <view class="home-actions">
            <button
              tabindex="0"
              role="button"
              class="quiet-action"
              @click="chooseTask"
              @keydown.enter.prevent="chooseTask"
              @keydown.space.prevent
              @keyup.space.prevent="chooseTask"
            >
              换个任务
            </button>
            <button
              tabindex="0"
              role="button"
              class="quiet-action"
              @click="go('/pages/manual/manual')"
              @keydown.enter.prevent="go('/pages/manual/manual')"
              @keydown.space.prevent
              @keyup.space.prevent="go('/pages/manual/manual')"
            >
              手动录入
            </button>
          </view>
          <button
            role="button"
            tabindex="0"
            class="home-map-entry"
            aria-label="个人易错地图"
            @keydown.enter.prevent="go('/pages/error-map/error-map')"
            @keydown.space.prevent
            @keyup.space.prevent="go('/pages/error-map/error-map')"
            @click="go('/pages/error-map/error-map')"
          >
            <view>
              <text>个人易错地图</text>
            </view>
            <uni-icons type="right" size="20" />
          </button>
        </view>
        <view v-if="otherTasks.length" class="task-list">
          <button
            tabindex="0"
            role="button"
            v-for="task in otherTasks"
            :key="task.key"
            class="task-row"
            @click="task.key === 'feedback' ? (showFeedback = !showFeedback) : go(task.url)"
            @keydown.enter.prevent="
              task.key === 'feedback' ? (showFeedback = !showFeedback) : go(task.url)
            "
            @keydown.space.prevent
            @keyup.space.prevent="
              task.key === 'feedback' ? (showFeedback = !showFeedback) : go(task.url)
            "
          >
            <view class="list-main">
              <text class="task-name">{{ task.title }}</text>
              <text class="task-detail">{{ task.detail }}</text>
            </view>
            <uni-icons type="right" size="22" color="var(--color-text-secondary)" />
          </button>
        </view>
        <view v-if="showFeedback && data.teacher_feedback" class="teacher-feedback">
          <view class="section-title"><text>教师反馈</text></view>
          <text class="feedback-conclusion">
            {{
              data.teacher_feedback.conclusion === 'confirmed_correct'
                ? '老师已确认正确'
                : '老师建议继续修改'
            }}
          </text>
          <text class="feedback-detail">{{ data.teacher_feedback.reason }}</text>
          <text v-if="data.teacher_feedback.student_hint" class="feedback-detail">
            提示：{{ data.teacher_feedback.student_hint }}
          </text>
          <text v-if="data.teacher_feedback.next_task" class="feedback-detail">
            下一步：{{ data.teacher_feedback.next_task }}
          </text>
        </view>
      </template>
    </view>
    <tab-bar current="home" />
  </view>
</template>

<script setup>
import { computed, ref } from 'vue'
import { onShow, onHide, onUnload } from '@dcloudio/uni-app'
import { getData } from '@/api/index.js'
import { go } from '@/utils/navigation.js'
import { useAppStore } from '@/store/index.js'
import { errorGroups } from '@/utils/repair.js'
import { studyEntries } from '@/constants/learning.js'

const store = useAppStore()
const data = ref(null)
const taskFocus = ref(null)
const loading = ref(true)
const error = ref('')
const preferences = ref(null),
  sources = ref([]),
  partialError = ref('')
let revision = 0
const recommendedGroup = computed(() =>
  errorGroups(sources.value).find(
    (group) => !preferences.value?.subject || group.subject === preferences.value.subject,
  ),
)
const goalLabel = computed(
  () =>
    ({ understand: '弄懂一道题', practice: '巩固一类题', review: '复习学过的内容' })[
      preferences.value?.goal
    ] || '按自己的节奏学习',
)
const gradeLabel = computed(() => data.value?.grade || store.user?.grade || '年级未设置')
const hasTodayReviews = computed(() => Number(data.value?.today_reviews || 0) > 0)
const focusKind = computed(() => {
  if (taskFocus.value) return 'task'
  if (data.value?.continue_learning) return 'continue'
  if (hasTodayReviews.value) return 'review'
  if (data.value?.teacher_assignment_count) return 'assignment'
  if (recommendedGroup.value) return 'repair'
  if (preferences.value?.subject) return 'starter'
  return 'capture'
})
const showFeedback = ref(false)
const otherTasks = computed(() => {
  const rows = []
  if (hasTodayReviews.value && focusKind.value !== 'review')
    rows.push({
      key: 'review',
      title: '今日复习',
      detail: `${data.value.today_reviews} 道题待复习`,
      url: '/pages/review/review',
    })
  if (data.value?.teacher_feedback)
    rows.push({ key: 'feedback', title: '老师有新反馈', detail: '查看建议，再继续修改' })
  if (data.value?.teacher_assignment_count && focusKind.value !== 'assignment')
    rows.push({
      key: 'assignment',
      title: '教师任务',
      detail: `${data.value.teacher_assignment_count} 项待完成`,
      url: '/pages/assignment/assignment',
    })
  if (data.value?.misconceptions?.length)
    rows.push({
      key: 'mistake',
      title: '需要巩固',
      detail: data.value.misconceptions[0].label,
      url: '/pages/problem/list',
    })
  return rows.slice(0, 2)
})
function chooseTask() {
  const choices = []
  if (hasTodayReviews.value) choices.push({ title: '到期复习', url: '/pages/review/review' })
  if (data.value?.teacher_assignment_count)
    choices.push({ title: '教师任务', url: '/pages/assignment/assignment' })
  choices.push(
    { title: '练一类题', url: '/pages/problem/list?purpose=practice' },
    { title: '查知识', url: '/pages/library/library' },
    { title: '录入错题', url: '/pages/capture/capture' },
  )
  const options = choices.slice(0, 3)
  uni.showActionSheet({
    itemList: options.map((x) => x.title),
    success: ({ tapIndex }) => go(options[tapIndex]?.url),
  })
}

function openKnowledge() {
  go(
    `/pages/library/library?subject=${encodeURIComponent(preferences.value?.subject || '')}&grade=${encodeURIComponent(gradeLabel.value === '年级未设置' ? '' : gradeLabel.value)}`,
  )
}

async function load() {
  const current = ++revision
  loading.value = true
  error.value = ''
  partialError.value = ''
  try {
    await store.loadUser()
    const [dashboard, tasks, preferenceResult, sourceResult] = await Promise.allSettled([
      getData('/dashboard'),
      getData('/learning-tasks', { silent: true }),
      getData('/student-preferences', { silent: true }),
      getData('/analytics/error-sources?days=90', { silent: true }),
    ])
    if (current !== revision) return
    if (dashboard.status === 'rejected') throw dashboard.reason
    data.value = dashboard.value
    preferences.value = preferenceResult.status === 'fulfilled' ? preferenceResult.value : null
    sources.value = sourceResult.status === 'fulfilled' ? sourceResult.value?.sources || [] : []
    if (tasks.status === 'rejected')
      partialError.value = '上次任务暂时无法读取，可以重试或选择其他学习入口。'
    else if (preferenceResult.status === 'rejected' || sourceResult.status === 'rejected')
      partialError.value = '部分学习建议暂时无法读取，其他功能仍可使用。'
    taskFocus.value =
      (tasks.status === 'fulfilled' ? tasks.value || [] : []).find((task) =>
        ['queued', 'running', 'waiting_student', 'needs_review', 'failed'].includes(task.status),
      ) || null
  } catch (err) {
    if (current === revision) error.value = err.message || '学习任务暂时无法加载，请重试'
  } finally {
    if (current === revision) loading.value = false
  }
}
onShow(load)
function clear() {
  revision++
  data.value = null
  taskFocus.value = null
  preferences.value = null
  sources.value = []
}
onHide(clear)
onUnload(clear)
</script>

<style scoped lang="scss">
.home-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: calc(28px + var(--status-bar-height, 0px)) var(--space-page) 8px;
}
.home-top-copy {
  flex: 1;
  min-width: 0;
}
.greeting {
  display: block;
  margin: 0;
  font-size: 30px;
  line-height: 1.25;
  font-weight: 700;
  letter-spacing: -0.035em;
}
.today-copy {
  display: block;
  margin-top: 8px;
  color: var(--color-text-secondary);
  font-size: 13px;
}
.search-action {
  margin: 0;
  padding: 0;
  background: var(--color-surface);
  width: 44px;
  height: 44px;
  min-width: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
}
.home-content {
  padding-top: 20px;
}
.home-direction {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  width: 100%;
  padding: 0 4px 20px;
  min-height: 44px;
  margin: 0;
  text-align: left;
  background: transparent;
  font-size: 13px;
  color: var(--color-text-secondary);
}
.home-direction > text:last-child {
  flex-shrink: 0;
  color: var(--color-primary);
}
.focus-card {
  padding: 32px;
  background: #edf5ff;
  color: var(--color-text-primary);
  border-radius: 24px;
}
.focus-symbol {
  margin-bottom: 24px;
  display: flex;
}
.focus-title {
  display: block;
  font-size: 26px;
  font-weight: 600;
  letter-spacing: -0.03em;
  line-height: 1.35;
  overflow-wrap: anywhere;
}
.focus-next {
  display: block;
  margin-top: 12px;
  font-size: 14px;
  color: var(--color-text-secondary);
  line-height: 1.6;
}
.focus-card .primary-btn {
  width: fit-content;
  max-width: 100%;
  min-height: 44px;
  padding: 12px 22px;
  margin-top: 24px;
  gap: 10px;
  font-size: 15px;
  border-radius: 999px;
}
.home-secondary {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: 16px;
}
.home-starter {
  margin: 0;
}
.home-starter .disclosure-link {
  padding: 20px 24px;
  background: var(--color-surface);
  border: 0;
  border-radius: 20px;
}
.entry-label {
  display: flex;
  align-items: center;
  gap: 14px;
}
.home-actions {
  display: flex;
  gap: 12px;
  margin: 0;
}
.home-actions .quiet-action {
  flex: 1;
  min-height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0;
  background: var(--color-surface);
  color: var(--color-primary);
  font-size: 14px;
  border-radius: 14px;
}
.home-map-entry {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  width: 100%;
  min-height: 68px;
  padding: 20px 24px;
  margin: 0;
  border-radius: 20px;
  background: var(--color-surface);
  text-align: left;
}
.home-map-entry text {
  display: block;
  font-size: 16px;
  font-weight: 400;
}
.home-partial-error {
  display: block;
  margin-bottom: 16px;
  font-size: 13px;
  color: var(--color-warning);
}
.task-list {
  background: var(--color-surface);
  padding: 0 24px;
  margin-top: 16px;
  border-radius: 20px;
}
.task-row {
  display: flex;
  align-items: center;
  gap: 16px;
  width: 100%;
  text-align: left;
  margin: 0;
  background: transparent;
  border-radius: 0;
  min-height: 72px;
  padding: 18px 0;
}
.task-row + .task-row {
  border-top: 1px solid var(--color-border);
}
.list-main {
  flex: 1;
  min-width: 0;
}
.task-name,
.task-detail {
  display: block;
}
.task-name {
  font-size: 16px;
}
.task-detail {
  font-size: 13px;
  line-height: 1.5;
  color: var(--color-text-secondary);
  margin-top: 4px;
}
.teacher-feedback {
  margin-top: 24px;
  padding: 24px;
  background: var(--color-surface);
  border-radius: 20px;
}
.feedback-conclusion,
.feedback-detail {
  display: block;
  font-size: 14px;
  line-height: 1.65;
}
.feedback-conclusion {
  font-weight: 500;
}
.feedback-detail {
  margin-top: 6px;
  color: var(--color-text-secondary);
}
@media (min-width: 1100px) {
  .home-top {
    padding-top: 48px;
  }
  .home-content {
    display: grid;
    grid-template-columns: minmax(0, 7fr) minmax(0, 5fr);
    gap: 16px;
    align-content: start;
    align-items: start;
  }
  .home-direction,
  .home-partial-error {
    grid-column: 1 / -1;
    padding-bottom: 0;
  }
  .focus-card {
    grid-column: 1;
    align-self: stretch;
    padding: 32px;
  }
  .home-secondary {
    margin-top: 0;
  }
  .home-actions {
    margin: 0;
  }

  .task-list,
  .teacher-feedback {
    grid-column: 1 / -1;
    margin-top: 0;
  }
}
.home-gateways {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  margin-bottom: 20px;
}
.study-gateway {
  display: flex;
  align-items: center;
  gap: 14px;
  width: 100%;
  margin: 0;
  padding: 22px 20px;
  min-height: 102px;
  border-radius: 22px;
  background: #e7f2ff;
  text-align: left;
}
.study-gateway.orange {
  background: #fff0da;
}
.study-gateway > view {
  flex: 1;
  min-width: 0;
}
.study-gateway text {
  display: block;
  font-size: 18px;
  font-weight: 600;
  color: #164f83;
}
.study-gateway.orange text {
  color: #874b18;
}
.home-map-entry {
  background: #eaf5ef;
}
.home-map-entry text {
  color: #246849;
}
@media (min-width: 1100px) {
  .home-gateways {
    grid-column: 1 / -1;
    margin-bottom: 4px;
  }
}
@media (max-width: 520px) {
  .study-gateway {
    flex-wrap: wrap;
    gap: 10px;
    padding: 20px;
  }
  .study-gateway > view {
    flex: 1 0 calc(100% - 50px);
  }
  .study-gateway > :last-child {
    display: none;
  }
  .study-gateway text {
    font-size: 17px;
  }
}
</style>
