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
        <uni-icons aria-hidden="true" type="search" size="24" color="#55565B" />
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
          <template v-if="focusKind === 'task'">
            <math-text
              class="focus-title"
              :text="taskFocus.question_title || '上次的错题还没完成'"
              inline
            />
            <button
              class="primary-btn"
              role="button"
              tabindex="0"
              @click="go(`/pages/task/task?id=${taskFocus.id}`)"
              @keydown.enter.prevent="go(`/pages/task/task?id=${taskFocus.id}`)"
            >
              继续订正
            </button>
          </template>
          <template v-else-if="focusKind === 'continue'">
            <math-text class="focus-title" :text="data.continue_learning.knowledge_point" inline />
            <math-text
              class="focus-next"
              :text="'下一步：' + data.continue_learning.next_step"
              inline
            />
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
              继续讲解
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
            <math-text class="focus-title" :text="recommendedGroup.label" inline />
            <text class="focus-next">
              {{ recommendedGroup.subject }} ·
              {{
                recommendedGroup.sources.length > 1
                  ? `${recommendedGroup.sources.length}道题中出现相同诊断线索`
                  : '来自你最近的一道题'
              }}
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
              查看学习安排
            </button>
          </template>
          <template v-else-if="focusKind === 'starter' && preferences.goal === 'practice'">
            <text class="focus-title">{{ preferences.subject }}练习</text>
            <text class="focus-next">
              {{ practiceSize(preferences.minutes) }} 道题 · {{ preferences.minutes }} 分钟
            </text>
            <button
              role="button"
              class="primary-btn"
              @click="go(preferredPracticeUrl(preferences, gradeLabel))"
              tabindex="0"
              @keydown.enter.prevent="go(preferredPracticeUrl(preferences, gradeLabel))"
              @keydown.space.prevent
              @keyup.space.prevent="go(preferredPracticeUrl(preferences, gradeLabel))"
            >
              开始练习
            </button>
          </template>
          <template v-else-if="focusKind === 'starter' && preferences.goal === 'review'">
            <text class="focus-title">
              {{
                hasTodayReviews
                  ? '今天有 ' + data.today_reviews + ' 道题待复习'
                  : '今天没有待复习题目'
              }}
            </text>
            <button
              role="button"
              class="primary-btn"
              tabindex="0"
              @click="go('/pages/review/review')"
              @keydown.enter.prevent="go('/pages/review/review')"
              @keydown.space.prevent
              @keyup.space.prevent="go('/pages/review/review')"
            >
              {{ hasTodayReviews ? '开始复习' : '查看复习安排' }}
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
              查看知识卡片
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
              <uni-icons
                aria-hidden="true"
                type="camera-filled"
                size="22"
                color="var(--color-surface)"
              />
              <text>拍照或选择图片</text>
            </button>
          </template>
        </view>

        <view class="home-secondary">
          <view class="home-gateways">
            <button
              role="button"
              v-for="entry in studyEntries"
              :key="entry.url"
              class="study-gateway"
              @click="
                go(
                  entry.url.includes('mode=practice') && preferences?.subject
                    ? preferredPracticeUrl(preferences, gradeLabel)
                    : entry.url,
                )
              "
            >
              <uni-icons
                aria-hidden="true"
                :type="entry.icon"
                size="23"
                color="var(--color-primary)"
              />
              <text>{{ entry.title }}</text>
              <uni-icons
                aria-hidden="true"
                type="right"
                size="16"
                color="var(--color-text-tertiary)"
              />
            </button>
          </view>
          <view v-if="focusKind === 'capture'" class="home-starter">
            <button
              aria-label="知识卡片"
              role="button"
              tabindex="0"
              class="disclosure-link"
              @keydown.enter.prevent="openKnowledge"
              @keydown.space.prevent
              @keyup.space.prevent="openKnowledge"
              @click="openKnowledge"
            >
              <view class="entry-label">
                <uni-icons
                  aria-hidden="true"
                  type="wallet"
                  size="22"
                  color="var(--color-primary)"
                />
                <text>知识卡片</text>
              </view>
              <uni-icons aria-hidden="true" type="right" size="18" />
            </button>
          </view>

          <button
            role="button"
            tabindex="0"
            class="home-map-entry"
            aria-label="易错地图"
            @keydown.enter.prevent="go('/pages/error-map/error-map')"
            @keydown.space.prevent
            @keyup.space.prevent="go('/pages/error-map/error-map')"
            @click="go('/pages/error-map/error-map')"
          >
            <view>
              <text>易错地图</text>
            </view>
            <uni-icons aria-hidden="true" type="right" size="20" />
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
              <math-text class="task-name" :text="task.title" inline />
              <math-text class="task-detail" :text="task.detail" inline />
            </view>
            <uni-icons
              aria-hidden="true"
              type="right"
              size="22"
              color="var(--color-text-secondary)"
            />
          </button>
        </view>
        <button
          role="button"
          class="home-direction"
          aria-label="学习设置"
          @click="go('/pages/preferences/preferences')"
        >
          <text>{{ preferences?.subject || '学习设置' }}</text>
          <text>
            学科、目标与时间
            <uni-icons aria-hidden="true" type="right" size="15" />
          </text>
        </button>
        <view v-if="showFeedback && data.teacher_feedback" class="teacher-feedback">
          <view class="section-title"><text>教师反馈</text></view>
          <text class="feedback-conclusion">
            {{
              data.teacher_feedback.conclusion === 'confirmed_correct'
                ? '老师已确认正确'
                : '老师建议继续修改'
            }}
          </text>
          <math-text class="feedback-detail" :text="data.teacher_feedback.reason" inline />
          <math-text
            v-if="data.teacher_feedback.student_hint"
            class="feedback-detail"
            :text="' 提示：' + data.teacher_feedback.student_hint"
            inline
          />
          <math-text
            v-if="data.teacher_feedback.next_task"
            class="feedback-detail"
            :text="' 下一步：' + data.teacher_feedback.next_task"
            inline
          />
        </view>
      </template>
    </view>
    <tab-bar current="home" />
  </view>
</template>

<script setup>
import MathText from '@/components/math-text/math-text.vue'
import { computed, ref } from 'vue'
import { onShow, onHide, onUnload } from '@dcloudio/uni-app'
import { getData } from '@/api/index.js'
import { go } from '@/utils/navigation.js'
import { useAppStore } from '@/store/index.js'
import { errorGroups } from '@/utils/repair.js'
import { studyEntries } from '@/constants/learning.js'
import { practiceSize, preferredPracticeUrl } from '@/utils/study-preferences.js'

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
const gradeLabel = computed(() => data.value?.grade || store.user?.grade || '年级未设置')
const hasTodayReviews = computed(() => Number(data.value?.today_reviews || 0) > 0)
const focusKind = computed(() => {
  if (taskFocus.value) return 'task'
  if (preferences.value?.subject && ['review', 'practice'].includes(preferences.value.goal))
    return 'starter'
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
    if (tasks.status === 'rejected') partialError.value = '上次的订正暂时无法读取。'
    else if (preferenceResult.status === 'rejected' || sourceResult.status === 'rejected')
      partialError.value = '部分学习记录暂时无法读取。'
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
  padding: calc(20px + var(--status-bar-height, 0px)) var(--space-page) 8px;
}
.greeting {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  line-height: 1.4;
}
.today-copy {
  display: block;
  color: var(--color-text-secondary);
  font-size: 13px;
  margin-top: 4px;
}
.search-action {
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  margin: 0;
  background: var(--color-surface);
  border-radius: 50%;
}
.focus-card {
  padding: 22px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-top: 1px solid var(--color-primary-border);
  border-radius: 12px;
}
.focus-title {
  display: block;
  font-size: 21px;
  font-weight: 600;
  line-height: 1.5;
  overflow-wrap: anywhere;
}
.focus-next {
  display: block;
  font-size: 14px;
  color: var(--color-text-secondary);
  margin-top: 8px;
}
.focus-card .primary-btn {
  margin-top: 22px;
  gap: 8px;
}
.home-secondary {
  margin-top: 18px;
}
.home-gateways {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.study-gateway {
  line-height: 1.5;
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  padding: 16px 12px;
  min-height: 64px;
  border: 1px solid var(--color-border);
  border-radius: 12px;
  background: var(--color-surface);
  text-align: left;
}
.study-gateway .uni-icons {
  flex: none;
  line-height: 1;
}
.study-gateway > text:not(.uni-icons) {
  flex: 1;
  font-size: 15px;
  font-weight: 500;
}
.home-map-entry,
.home-starter .disclosure-link {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  min-height: 58px;
  margin: 10px 0 0;
  padding: 12px 0;
  background: transparent;
  color: var(--color-text-primary);
  font-size: 15px;
  text-align: left;
  border-bottom: 1px solid var(--color-border);
  border-radius: 0;
}
.entry-label {
  display: flex;
  align-items: center;
  gap: 8px;
}
.home-direction {
  display: flex;
  justify-content: space-between;
  width: 100%;
  min-height: 48px;
  gap: 12px;
  padding: 12px 0;
  margin: 12px 0 0;
  font-size: 13px;
  color: var(--color-text-secondary);
  background: transparent;
  text-align: left;
}
.task-list {
  margin-top: 12px;
}
.task-row {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  min-height: 64px;
  padding: 14px 0;
  margin: 0;
  text-align: left;
  border-bottom: 1px solid var(--color-border);
  border-radius: 0;
  background: transparent;
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
  font-size: 15px;
}
.task-detail {
  margin-top: 3px;
  font-size: 13px;
  color: var(--color-text-secondary);
}
.home-partial-error {
  margin-bottom: 12px;
  font-size: 13px;
  color: var(--color-warning);
}
.teacher-feedback {
  padding: 16px;
  border: 1px solid var(--color-border);
  border-radius: 12px;
  background: var(--color-surface);
}
.feedback-conclusion,
.feedback-detail {
  display: block;
  font-size: 14px;
}
.feedback-detail {
  margin-top: 8px;
  color: var(--color-text-secondary);
}
@media (min-width: 1100px) {
  .home-top {
    padding-top: 28px;
  }
  .home-content {
    display: grid;
    grid-template-columns: minmax(0, 3fr) minmax(0, 2fr);
    gap: 20px;
    align-items: start;
  }
  .focus-card {
    grid-column: 1;
    grid-row: 1 / 3;
  }
  .home-secondary {
    margin-top: 0;
  }
  .home-partial-error,
  .teacher-feedback {
    grid-column: 1 / -1;
  }
  .task-list,
  .home-direction {
    grid-column: 2;
    margin-top: 0;
  }
}
@media (max-width: 360px) {
  .study-gateway {
    gap: 6px;
    padding: 14px 10px;
  }
  .study-gateway > :last-child {
    display: none;
  }
}
</style>
