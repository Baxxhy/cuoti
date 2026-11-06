<template>
  <view class="page bank-page">
    <app-header :title="mode === 'exam' ? '模拟考试' : '题库练习'" back />
    <view class="page-content">
      <view class="bank-switch segmented">
        <button
          :class="{ active: mode === 'practice' }"
          :aria-pressed="mode === 'practice'"
          role="button"
          tabindex="0"
          @click="switchMode('practice')"
          @keydown.enter="switchMode('practice')"
          @keydown.space.prevent
          @keyup.space.prevent="switchMode('practice')"
        >
          题库练习
        </button>
        <button
          :class="{ active: mode === 'exam' }"
          :aria-pressed="mode === 'exam'"
          role="button"
          tabindex="0"
          @click="switchMode('exam')"
          @keydown.enter="switchMode('exam')"
          @keydown.space.prevent
          @keyup.space.prevent="switchMode('exam')"
        >
          模拟考试
        </button>
      </view>
      <view class="bank-filters">
        <scroll-view scroll-x :show-scrollbar="false">
          <view class="bank-subjects">
            <button
              role="button"
              v-for="value in ['全部', ...subjects]"
              :key="value"
              :class="{ selected: filters.subject === (value === '全部' ? '' : value) }"
              @click="setFilter('subject', value === '全部' ? '' : value)"
            >
              {{ value }}
            </button>
          </view>
        </scroll-view>
      </view>
      <state-panel
        v-if="loading || error"
        :state="error ? 'error' : 'loading'"
        :message="error"
        @retry="load"
      />
      <template v-else-if="data">
        <view v-if="mode === 'exam'" class="exam-setup card">
          <text class="section-heading">考试设置</text>
          <text class="setting-label">题数</text>
          <view class="choice-row">
            <button
              role="button"
              v-for="n in [5, 10, 20]"
              :key="n"
              :class="{ chosen: count === n }"
              :disabled="data.total < n || busy"
              @click="count = n"
            >
              {{ n }} 题
            </button>
          </view>
          <text class="setting-label">考试时间</text>
          <view class="choice-row">
            <button
              role="button"
              v-for="n in [10, 20, 45]"
              :key="n"
              :class="{ chosen: minutes === n }"
              :disabled="busy"
              @click="minutes = n"
            >
              {{ n }} 分钟
            </button>
          </view>
          <button
            role="button"
            class="primary-btn exam-start"
            :disabled="busy || data.total < count"
            @click="start()"
          >
            {{ busy ? '正在准备试卷…' : '开始模拟考试' }}
          </button>
        </view>
        <template v-else>
          <view class="bank-search">
            <uni-icons
              aria-hidden="true"
              type="search"
              size="20"
              color="var(--color-text-secondary)"
            />
            <input
              v-model="search"
              aria-label="搜索题库"
              placeholder="搜索题目"
              confirm-type="search"
              @confirm="applySearch"
            />
            <button role="button" class="text-search" @click="applySearch">搜索</button>
          </view>
          <view class="bank-list-heading">
            <text>选择题目</text>
            <button role="button" :disabled="busy || data.total < practiceCount" @click="start()">
              练 {{ practiceCount }} 题
              <uni-icons aria-hidden="true" type="right" size="14" />
            </button>
          </view>
          <view v-if="!data.questions.length" class="empty card">
            <text>
              {{
                filters.search || filters.source_id
                  ? '没有找到符合条件的题目'
                  : `暂无可用的${data.scope_label || studentGrade}${filters.subject}题目`
              }}
            </text>
          </view>
          <button
            role="button"
            v-for="question in data.questions"
            :key="question.id"
            class="bank-question"
            :disabled="busy || question.image_layout_review"
            @click="start(question.id)"
          >
            <view class="question-meta">
              <text class="subject-badge">{{ question.subject }}</text>
              <text>{{ questionTypeLabel(question.question_type) }}</text>
              <uni-icons
                aria-hidden="true"
                class="question-arrow"
                type="arrowright"
                size="20"
                color="var(--color-primary)"
              />
            </view>
            <view class="bank-question-preview">
              <math-text
                class="bank-question-text"
                :subject="question.subject"
                :text="question.preview_text || question.question_text"
                inline
              />
              <view v-if="questionImageUrls(question).length" class="bank-question-images">
                <image
                  v-if="!failedImages[questionImageUrls(question)[0]]"
                  :src="mediaUrl(questionImageUrls(question)[0])"
                  mode="aspectFit"
                  alt="题图预览"
                  @error="failedImages[questionImageUrls(question)[0]] = true"
                />
                <text v-else class="image-error">预览暂不可用</text>
                <text v-if="questionImageUrls(question).length > 1" class="image-count">
                  {{ questionImageUrls(question).length }} 张题图
                </text>
              </view>
            </view>
            <text v-if="question.image_layout_review" class="image-error">题图待核对</text>
          </button>
          <view v-if="data.total > 20" class="bank-paging">
            <button role="button" :disabled="filters.page <= 1" @click="changePage(-1)">
              上一页
            </button>
            <text>{{ filters.page }} / {{ Math.ceil(data.total / 20) }}</text>
            <button
              role="button"
              :disabled="filters.page * 20 >= data.total"
              @click="changePage(1)"
            >
              下一页
            </button>
          </view>
        </template>
        <text v-if="actionError" class="account-notice" role="alert">{{ actionError }}</text>
      </template>
      <view v-if="visibleHistory.length" class="session-history">
        <view class="section-title">
          <text>{{ mode === 'exam' ? '考试记录' : '练习记录' }}</text>
        </view>
        <button
          role="button"
          v-for="item in visibleHistory"
          :key="item.id"
          class="session-record"
          @click="go(`/pages/study-session/study-session?id=${item.id}`)"
        >
          <view>
            <math-text :text="item.title" inline />
            <small>{{ item.question_count }} 题 · {{ shortDate(item.created_at) }}</small>
          </view>
          <text class="record-status" :class="{ done: item.status === 'submitted' }">
            {{
              item.status === 'submitted'
                ? item.results?.excluded && !item.results?.max_score
                  ? '已暂停'
                  : `${item.results?.score ?? 0} / ${item.results?.max_score ?? 0} 分`
                : '继续作答'
            }}
          </text>
          <uni-icons aria-hidden="true" type="right" size="16" color="var(--color-text-tertiary)" />
        </button>
      </view>
      <button
        role="button"
        v-if="mode === 'exam'"
        class="disclosure-link old-papers"
        @click="go('/pages/paper/paper-center')"
      >
        我的错题组卷
        <uni-icons aria-hidden="true" type="right" size="18" />
      </button>
    </view>
    <tab-bar current="learning" />
  </view>
</template>
<script setup>
import MathText from '@/components/math-text/math-text.vue'
import { computed, ref } from 'vue'
import { onLoad, onShow } from '@dcloudio/uni-app'
import { getData, postData, mediaUrl } from '@/api/index.js'
import { go } from '@/utils/navigation.js'
import { questionTypeLabel } from '@/utils/question.js'
import { questionImageUrls } from '@/utils/question-content'
const mode = ref('practice'),
  data = ref(null),
  loading = ref(false),
  error = ref(''),
  busy = ref(false),
  actionError = ref(''),
  history = ref([]),
  search = ref('')
const failedImages = ref({})
const filters = ref({
  subject: '',
  grade_band: '',
  source_id: '',
  search: '',
  page: 1,
  shuffle_seed: Date.now() % 2147483647,
})
const practiceCount = ref(5)
const count = ref(5),
  minutes = ref(20)
const subjects = ['语文', '数学', '英语', '物理', '化学', '生物', '历史', '地理', '思想政治']
const studentGrade = ref('')
const visibleHistory = computed(() =>
  history.value.filter((x) => x.mode === mode.value).slice(0, 8),
)
let revision = 0
let defaultsLoaded = false
let initialQuery = {}
function shortDate(value) {
  return String(value || '').slice(0, 10)
}
async function load() {
  const current = ++revision
  loading.value = true
  error.value = ''
  try {
    if (!defaultsLoaded) {
      const preferences = await getData('/student-preferences', { silent: true })
      if (current !== revision) return
      studentGrade.value = preferences.grade || ''
      filters.value.subject = initialQuery.subject || preferences.subject || '数学'
      filters.value.grade_band = /^高/.test(preferences.grade || '')
        ? '高中'
        : /^初/.test(preferences.grade || '')
          ? '初中'
          : ''
      defaultsLoaded = true
    }
    const query = Object.entries(filters.value)
      .map(([key, value]) => `${key}=${encodeURIComponent(value)}`)
      .join('&')
    const bank = await getData(`/study-bank?${query}`, { silent: true })
    if (current !== revision) return
    data.value = bank
  } catch (e) {
    if (current === revision) error.value = e.message || '题库暂时无法读取'
  } finally {
    if (current === revision) loading.value = false
  }
}
function setFilter(key, value) {
  filters.value[key] = value
  if (key === 'subject' && value === '')
    filters.value.shuffle_seed = (filters.value.shuffle_seed + 1) % 2147483647
  filters.value.page = 1
  load()
}
function switchMode(value) {
  mode.value = value
  if (value === 'exam' && filters.value.search) {
    search.value = ''
    setFilter('search', '')
  }
}
function applySearch() {
  setFilter('search', search.value.trim())
}
function changePage(offset) {
  filters.value.page += offset
  load()
  uni.pageScrollTo({ scrollTop: 0, duration: 150 })
}
async function start(questionId) {
  if (busy.value) return
  busy.value = true
  actionError.value = ''
  try {
    const session = await postData(
      '/study-sessions',
      {
        mode: mode.value,
        subject: filters.value.subject,
        grade_band: filters.value.grade_band,
        source_id: filters.value.source_id,
        search: filters.value.search,
        count: mode.value === 'exam' ? count.value : practiceCount.value,
        selection_strategy: mode.value === 'practice' && !questionId ? 'adaptive' : 'random',
        minutes: minutes.value,
        ...(questionId ? { question_ids: [questionId] } : {}),
      },
      { silent: true },
    )
    go(`/pages/study-session/study-session?id=${session.id}`)
  } catch (e) {
    actionError.value = e.message || '暂时无法开始，请重试'
  } finally {
    busy.value = false
  }
}
onLoad((query) => {
  initialQuery = query
  mode.value = query.mode === 'exam' ? 'exam' : 'practice'
  if (query.subject) filters.value.subject = query.subject
  if (query.grade_band) filters.value.grade_band = query.grade_band
  if (query.count && [3, 5, 10].includes(Number(query.count)))
    practiceCount.value = Number(query.count)
  if (query.minutes && [5, 10, 20].includes(Number(query.minutes)))
    minutes.value = Number(query.minutes)
  if (query.source_id) filters.value.source_id = query.source_id
})
onShow(() => {
  load()
  // History does not block the question list or reload on every filter change.
  getData('/study-sessions', { silent: true })
    .then((records) => {
      history.value = records
    })
    .catch(() => {})
})
</script>
<style scoped lang="scss">
.bank-switch {
  max-width: 360px;
  margin-bottom: 24px;
}
.bank-intro {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 28px;
  border-radius: 24px;
  background: #e8f3ff;
  margin-bottom: 24px;
}
.bank-intro.exam {
  background: var(--color-primary-soft);
}
.bank-title {
  display: block;
  font-size: 24px;
  font-weight: 650;
  letter-spacing: -0.03em;
}
.bank-count {
  display: block;
  margin-top: 10px;
  font-size: 14px;
  color: #3e6485;
}
.exam .bank-count {
  color: #845a29;
}
.bank-filters {
  margin-bottom: 24px;
}
.bank-subjects {
  display: flex;
  gap: 8px;
  white-space: nowrap;
  padding-bottom: 12px;
}
.bank-subjects button {
  flex: none;
  margin: 0;
  min-height: 40px;
  padding: 8px 16px;
  border-radius: 12px;
  background: #fff;
  color: var(--color-text-secondary);
  font-size: 14px;
}
.bank-subjects button.selected {
  background: var(--color-primary);
  color: #fff;
}
.bank-search {
  display: flex;
  align-items: center;
  gap: 10px;
  background: #fff;
  border-radius: 14px;
  padding: 4px 14px;
  margin-bottom: 24px;
}
.bank-search input {
  flex: 1;
  min-width: 0;
  min-height: 44px;
  font-size: 15px;
}
.text-search {
  padding: 8px 0;
  background: transparent;
  color: var(--color-primary);
  font-size: 14px;
  margin: 0;
}
.bank-list-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 12px;
  font-size: 16px;
  font-weight: 600;
}
.bank-list-heading button {
  flex: none;
  margin: 0;
  padding: 8px 0;
  background: transparent;
  color: var(--color-primary);
  font-size: 13px;
}
.bank-question {
  display: block;
  width: 100%;
  margin: 12px 0;
  padding: 16px;
  border-radius: var(--radius-card);
  background: #fff;
  text-align: left;
  line-height: 1.6;
}
.question-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
  color: var(--color-text-secondary);
  font-size: 12px;
}
.subject-badge {
  color: #176cbb;
  background: #edf5ff;
  border-radius: 6px;
  padding: 2px 8px;
}
.bank-question-text {
  font-size: 16px;
  flex: 1;
  min-width: 0;
  // 公式与多行题干高度不固定，跟随内容展开，避免截断文字和分式。
}
.bank-question-preview {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}
.bank-question-images {
  display: flex;
  flex-direction: column;
  flex: 0 0 88px;
  width: 88px;
  gap: 4px;
}
.bank-question-images image {
  display: block;
  width: 88px;
  height: 88px;
}
.image-count {
  font-size: 12px;
  color: var(--color-text-secondary);
  text-align: center;
}
.image-error {
  font-size: 12px;
  color: var(--color-primary);
}
.question-arrow {
  margin-left: auto;
}
.bank-paging {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin: 24px 0;
  font-size: 13px;
  color: var(--color-text-secondary);
}
.bank-paging button {
  margin: 0;
  background: #fff;
  font-size: 14px;
  border-radius: 12px;
}
.section-heading {
  font-size: 20px;
  font-weight: 600;
  display: block;
}
.setting-label {
  display: block;
  margin: 24px 0 10px;
  font-size: 14px;
}
.choice-row {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.choice-row button {
  border: 1px solid transparent;
  margin: 0;
  min-height: 44px;
  padding: 10px 16px;
  border-radius: 12px;
  background: var(--color-bg);
  font-size: 14px;
}
.choice-row button.chosen {
  background: var(--color-primary-soft);
  color: var(--color-primary);
  border-color: var(--color-primary-border);
}
.exam-start {
  background: var(--color-primary);
}
.session-history {
  margin-top: 32px;
}
.session-record {
  display: flex;
  align-items: center;
  gap: 12px;
  text-align: left;
  width: 100%;
  margin: 10px 0;
  padding: 18px 20px;
  background: #fff;
  border-radius: 16px;
  font-size: 15px;
}
.session-record > view {
  flex: 1;
  min-width: 0;
}
.session-record small {
  display: block;
  margin-top: 5px;
  font-size: 12px;
  color: var(--color-text-secondary);
}
.record-status {
  font-size: 13px;
  color: var(--color-primary);
}
.record-status.done {
  color: #267350;
}
.old-papers {
  margin-top: 28px;
}
@media (min-width: 1100px) {
  .bank-intro {
    padding: 32px;
  }
  .exam-setup {
    max-width: 640px;
  }
}
@media (max-width: 360px) {
  .bank-list-heading {
    align-items: flex-start;
    flex-direction: column;
    gap: 0;
  }
}
</style>
