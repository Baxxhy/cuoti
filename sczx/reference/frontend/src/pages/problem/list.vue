<template>
  <view class="page problem-page">
    <app-header
      :title="purpose === 'practice' ? '选择错题' : '错题本'"
      :back="purpose === 'practice'"
      back-fallback="/pages/learning/learning"
    >
      <button
        tabindex="0"
        role="button"
        class="header-add"
        @click="go('/pages/capture/capture')"
        @keydown.enter.prevent="go('/pages/capture/capture')"
        @keydown.space.prevent
        @keyup.space.prevent="go('/pages/capture/capture')"
      >
        录入
      </button>
    </app-header>
    <view class="page-content problem-content">
      <view class="inline-search">
        <input
          v-model="filters.search"
          placeholder="搜索题目、知识点或错因"
          aria-label="搜索错题"
          confirm-type="search"
          @confirm="load"
        />
        <button
          tabindex="0"
          role="button"
          class="search-button"
          @click="load"
          @keydown.enter.prevent="load"
          @keydown.space.prevent
          @keyup.space.prevent="load"
        >
          搜索
        </button>
      </view>
      <scroll-view scroll-x class="subject-scroll" :show-scrollbar="false">
        <view class="subject-tabs">
          <button
            tabindex="0"
            role="button"
            v-for="subject in ['全部', ...subjects]"
            :key="subject"
            class="subject-tab"
            :class="{ active: filters.subject === (subject === '全部' ? '' : subject) }"
            @click="selectSubject(subject)"
            @keydown.enter.prevent="selectSubject(subject)"
            @keydown.space.prevent
            @keyup.space.prevent="selectSubject(subject)"
          >
            {{ subject }}
          </button>
        </view>
      </scroll-view>
      <view class="list-toolbar">
        <text>{{ visible.length }} 道题</text>
        <button
          tabindex="0"
          role="button"
          class="text-button"
          :aria-expanded="showFilters"
          @click="openFilters"
          @keydown.enter.prevent="openFilters"
          @keydown.space.prevent
          @keyup.space.prevent="openFilters"
        >
          筛选{{ activeFilterCount ? ` · ${activeFilterCount}` : '' }}
        </button>
        <button
          tabindex="0"
          role="button"
          v-if="visible.length"
          class="text-button"
          @click="exportSelection"
          @keydown.enter.prevent="exportSelection"
          @keydown.space.prevent
          @keyup.space.prevent="exportSelection"
        >
          按当前条件组卷
        </button>
      </view>
      <view v-if="activeFilterCount" class="selected-filters">
        <text>{{ filterSummary }}</text>
        <button
          tabindex="0"
          role="button"
          class="text-button"
          @click="clearFilters"
          @keydown.enter.prevent="clearFilters"
          @keydown.space.prevent
          @keyup.space.prevent="clearFilters"
        >
          清除筛选
        </button>
      </view>
      <view
        v-if="showFilters"
        class="filter-sheet"
        role="region"
        aria-label="错题筛选"
        @keydown.esc="showFilters = false"
      >
        <text class="sheet-title">筛选与整理</text>
        <view class="filter-controls">
          <picker
            :range="stageLabels"
            :value="stageCodes.indexOf(draft.stage)"
            @change="draft.stage = stageCodes[Number($event.detail.value)]"
          >
            <view class="filter-control">
              {{ stageLabels[stageCodes.indexOf(draft.stage)] }}
              <uni-icons aria-hidden="true" type="bottom" size="14" />
            </view>
          </picker>
          <button
            tabindex="0"
            role="button"
            class="filter-control"
            :class="{ active: draft.favorite }"
            :aria-pressed="draft.favorite"
            @click="draft.favorite = !draft.favorite"
            @keydown.enter.prevent="draft.favorite = !draft.favorite"
            @keydown.space.prevent
            @keyup.space.prevent="draft.favorite = !draft.favorite"
          >
            仅收藏
          </button>
          <button
            tabindex="0"
            role="button"
            class="filter-control"
            :class="{ active: draft.due }"
            :aria-pressed="draft.due"
            @click="draft.due = !draft.due"
            @keydown.enter.prevent="draft.due = !draft.due"
            @keydown.space.prevent
            @keyup.space.prevent="draft.due = !draft.due"
          >
            到期复习
          </button>
          <picker
            :range="groupLabels"
            :value="groupCodes.indexOf(draft.group)"
            @change="draft.group = groupCodes[Number($event.detail.value)]"
          >
            <view class="filter-control">
              {{ groupLabels[groupCodes.indexOf(draft.group)] }}
              <uni-icons aria-hidden="true" type="bottom" size="14" />
            </view>
          </picker>
        </view>
        <view class="sheet-actions">
          <button
            tabindex="0"
            role="button"
            class="secondary-btn"
            @click="showFilters = false"
            @keydown.enter.prevent="showFilters = false"
            @keydown.space.prevent
            @keyup.space.prevent="showFilters = false"
          >
            取消
          </button>
          <button
            tabindex="0"
            role="button"
            class="primary-btn"
            @click="applyFilters"
            @keydown.enter.prevent="applyFilters"
            @keydown.space.prevent
            @keyup.space.prevent="applyFilters"
          >
            应用筛选
          </button>
        </view>
      </view>
      <text v-if="filters.group !== 'none'" class="group-help">
        相同标签只用于整理，每道题仍需单独验证。
      </text>
      <state-panel
        v-if="loading || error"
        :state="error ? 'error' : 'loading'"
        :message="error"
        @retry="load"
      />
      <template v-else>
        <view v-for="group in groups" :key="group.key" class="problem-group">
          <view v-if="group.title" class="group-heading">
            <b><math-text :text="group.title" inline /></b>
            <text>
              {{ group.subject }} · {{ group.grade || '未设置年级' }} · {{ group.items.length }} 道
            </text>
          </view>
          <view class="problem-list">
            <button
              tabindex="0"
              role="button"
              v-for="item in group.items"
              :key="item.id"
              class="problem-card"
              @click="open(item)"
              @keydown.enter.prevent="open(item)"
              @keydown.space.prevent
              @keyup.space.prevent="open(item)"
            >
              <view class="problem-meta">
                <text>
                  {{ item.subject }}
                  <template v-if="item.grade">· {{ item.grade }}</template>
                </text>
                <text v-if="item.favorite">已收藏</text>
              </view>
              <view class="problem-body">
                <math-text
                  class="problem-text"
                  :text="item.question_text || '待核对的题目'"
                  inline
                />
                <image
                  v-if="item.thumbnail_url"
                  :src="mediaUrl(item.thumbnail_url)"
                  mode="aspectFill"
                />
              </view>
              <view class="problem-facts">
                <text>{{ questionStatus(item) }}</text>
              </view>
            </button>
          </view>
        </view>
        <view v-if="!visible.length" class="empty empty-problems">
          <text>{{ hasFilters ? '没有符合条件的错题' : '还没有错题' }}</text>
          <text v-if="hasFilters" class="empty-hint">试试减少筛选条件，或换个关键词。</text>
          <button
            tabindex="0"
            role="button"
            v-if="hasFilters"
            class="small-btn"
            @click="clearFilters"
            @keydown.enter.prevent="clearFilters"
            @keydown.space.prevent
            @keyup.space.prevent="clearFilters"
          >
            清除筛选
          </button>
          <button
            tabindex="0"
            role="button"
            v-else
            class="small-btn"
            @click="go('/pages/capture/capture')"
            @keydown.enter.prevent="go('/pages/capture/capture')"
            @keydown.space.prevent
            @keyup.space.prevent="go('/pages/capture/capture')"
          >
            添加错题
          </button>
        </view>
      </template>
    </view>
    <tab-bar current="problems" />
  </view>
</template>
<script setup>
import { computed, reactive, ref, watch } from 'vue'
import MathText from '@/components/math-text/math-text.vue'
import { onLoad, onShow } from '@dcloudio/uni-app'
import { questionRoute } from '@/utils/question.js'
import { getData, mediaUrl } from '@/api/index.js'
import { CORE_SUBJECTS as subjects } from '@/constants/education.js'
import { go } from '@/utils/navigation.js'
import { useAppStore } from '@/store/index.js'
import {
  filterQuestions,
  groupQuestions,
  hasDiagnosis,
  needsConfirmation,
  notebookView,
  saveNotebookView,
  questionSearchURL,
  questionStatus,
  paperURL,
} from '@/utils/learning.js'
const store = useAppStore()
const items = ref([]),
  loading = ref(true),
  error = ref(''),
  purpose = ref('')
const defaults = { subject: '', search: '', stage: '', favorite: false, due: false, group: 'none' }
const filters = reactive({ ...defaults })
const draft = reactive({ ...defaults })
const showFilters = ref(false)
const stageCodes = ['', 'confirm', 'diagnose', 'learn'],
  stageLabels = ['全部处理状态', '待核对', '待找错因', '继续学习']
const groupCodes = ['none', 'knowledge', 'cause'],
  groupLabels = ['按时间查看', '按知识点分组', '按错因分组']
const visible = computed(() => filterQuestions(items.value, filters))
const groups = computed(() => groupQuestions(visible.value, filters.group))
const activeFilterCount = computed(
  () =>
    [filters.stage, filters.favorite, filters.due, filters.group !== 'none'].filter(Boolean).length,
)
const filterSummary = computed(() =>
  [
    filters.stage && stageLabels[stageCodes.indexOf(filters.stage)],
    filters.favorite && '仅收藏',
    filters.due && '到期复习',
    filters.group !== 'none' && groupLabels[groupCodes.indexOf(filters.group)],
  ]
    .filter(Boolean)
    .join(' · '),
)
function openFilters() {
  Object.assign(draft, filters)
  showFilters.value = !showFilters.value
}
function applyFilters() {
  Object.assign(filters, {
    stage: draft.stage,
    favorite: draft.favorite,
    due: draft.due,
    group: draft.group,
  })
  showFilters.value = false
}
const hasFilters = computed(
  () =>
    filters.subject ||
    filters.search ||
    filters.stage ||
    filters.favorite ||
    filters.due ||
    filters.group !== 'none',
)
let requestId = 0,
  initialized = false,
  routeOptions = {}
watch(filters, () => {
  if (initialized) saveNotebookView(store.user?.id, filters)
})
onLoad((q) => {
  routeOptions = q
  purpose.value = q.purpose || ''
})
async function load() {
  const current = ++requestId
  loading.value = true
  error.value = ''
  try {
    if (!store.user) await store.loadUser()
    if (!initialized) {
      Object.assign(filters, notebookView(store.user?.id))
      // Explicit links start from their own scope, not a previous unrelated filter.
      if (Object.keys(routeOptions).length) {
        Object.assign(filters, defaults, {
          subject: routeOptions.subject || '',
          search: routeOptions.search || '',
          favorite: routeOptions.favorite === '1',
          due: routeOptions.due === '1',
        })
      }
      initialized = true
    }
    const result = await getData(questionSearchURL(filters))
    if (current === requestId) items.value = result
  } catch (err) {
    if (current === requestId) error.value = err.message || '错题暂时无法加载，请重试'
  } finally {
    if (current === requestId) loading.value = false
  }
}
function selectSubject(value) {
  filters.subject = value === '全部' ? '' : value
  load()
}
function clearFilters() {
  showFilters.value = false
  Object.assign(filters, defaults)
  load()
}
function exportSelection() {
  // All visible IDs are transferred; limit only protects URL size and is explicit.
  if (visible.value.length > 50) {
    uni.showToast({ title: '请缩小到50道以内后组卷', icon: 'none' })
    return
  }
  go(paperURL({ subject: filters.subject, ids: visible.value.map((item) => item.id) }))
}
function open(item) {
  if (purpose.value === 'practice' && !needsConfirmation(item) && hasDiagnosis(item))
    go(`/pages/practice/practice?id=${encodeURIComponent(item.id)}`)
  else go(questionRoute(item))
}
onShow(load)
</script>
<style scoped lang="scss">
.filter-sheet {
  padding: 18px;
  margin-bottom: 20px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 12px;
}
.sheet-title {
  font-size: 18px;
  font-weight: 600;
}
.sheet-actions {
  display: flex;
  gap: 12px;
}
.sheet-actions button {
  flex: 1;
}
.selected-filters {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 14px;
  color: var(--color-text-secondary);
  margin-bottom: 12px;
}
.selected-filters > text {
  flex: 1;
}

.problem-content {
  padding-top: 24rpx;
}
.inline-search {
  min-height: 84rpx;
  display: flex;
  align-items: center;
  gap: 14rpx;
  padding: 0 22rpx;
  border: 1rpx solid var(--color-border);
  border-radius: 12px;
  background: var(--color-surface);
  color: var(--color-text-secondary);
  font-size: 25rpx;
}
.subject-scroll {
  white-space: nowrap;
  margin-top: 16rpx;
  border-bottom: 1rpx solid var(--color-border);
}
.subject-tabs {
  display: flex;
  gap: 30rpx;
  white-space: nowrap;
}
.subject-tab {
  background: transparent;
  border-radius: 0;
  margin: 0;
  line-height: 1.5;

  flex: none;
  min-height: 88rpx;
  display: inline-flex;
  align-items: center;
  border-bottom: 3rpx solid transparent;
  color: var(--color-text-secondary);
  font-size: 26rpx;
  padding: 0 4rpx;
}
.subject-tab.active {
  border-bottom-color: var(--color-primary);
  color: var(--color-primary);
  font-weight: 600;
}
.list-count {
  display: block;
  padding: 22rpx 0 4rpx;
  font-size: 23rpx;
  color: var(--color-text-secondary);
}
.problem-card {
  display: block;
  width: 100%;
  text-align: left;
  background: var(--color-surface);
  border-radius: 20px;
  margin: 12px 0;
  line-height: 1.6;

  padding: 20px 24px;
  border: 0;
}
.problem-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
  font-size: 22rpx;
  color: var(--color-text-secondary);
}
.mastery-status {
  white-space: nowrap;
}
.problem-topic {
  display: block;
  margin-top: 10rpx;
  font-size: 29rpx;
  font-weight: 600;
  line-height: 1.5;
}
.problem-body {
  display: flex;
  gap: 20rpx;
  align-items: flex-start;
  margin-top: 8rpx;
}
.problem-body image {
  width: 108rpx;
  height: 88rpx;
  flex: none;
  border: 1rpx solid var(--color-border);
  border-radius: 8rpx;
  background: var(--color-surface);
}
.problem-text {
  flex: 1;
  min-width: 0;
  font-size: 15px;
  line-height: 1.9;
  font-weight: 500;
  color: var(--color-text-primary);
}
.problem-facts {
  margin-top: 14rpx;
  font-size: 23rpx;
  line-height: 1.6;
  color: var(--color-text-secondary);
}
.problem-facts text {
  display: block;
}
.diagnosis-summary {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.review-due {
  margin-top: 4rpx;
}
.empty-problems {
  padding: 28px 0;
  margin-top: 24px;
  background: transparent;
  text-align: left;
}
.empty-problems > text {
  margin-top: 14rpx;
  font-size: 28rpx;
  color: var(--color-text-primary);
}
.empty-problems .empty-hint {
  font-size: 25rpx;
  color: var(--color-text-secondary);
  margin-top: 6rpx;
}
.empty-problems .small-btn {
  margin-top: 26rpx;
}

.problem-card::after,
.subject-tab::after,
.text-button::after,
.header-add::after {
  border: 0;
}
.inline-search input {
  flex: 1;
  min-width: 0;
  font-size: 15px;
}
.inline-search:focus-within {
  border-color: var(--color-primary);
}
.search-button,
.header-add {
  font-size: 14px;
  min-height: 44px;
  line-height: 44px;
  margin: 0;
  background: transparent;
  color: var(--color-primary);
}
.filter-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
}
.filter-control {
  padding: 0 10px;
  min-height: 44px;
  line-height: 44px;
  font-size: 13px;
  background: white;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  margin: 0;
}
.filter-control.active {
  color: var(--color-primary);
  border-color: var(--color-primary);
}
.list-toolbar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 13px;
  color: var(--color-text-secondary);
}
.text-button {
  font-size: 13px;
  padding: 0 6px;
  min-height: 44px;
  line-height: 44px;
  background: transparent;
  color: var(--color-primary);
  margin: 0;
}
.group-heading {
  display: grid;
  gap: 4px;
  padding: 16px 0 8px;
  font-size: 15px;
}
.group-heading text,
.group-help {
  font-size: 13px;
  color: var(--color-text-secondary);
}
</style>
