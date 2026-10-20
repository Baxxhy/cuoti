<template>
  <view class="page review-search-page">
    <app-header title="查找复习题" back back-fallback="/pages/review/review" />
    <view class="page-content">
      <view class="search-row" role="search">
        <input
          v-model="query"
          aria-label="搜索复习题"
          placeholder="搜索题目或知识点"
          confirm-type="search"
          maxlength="150"
          @confirm="search()"
        />
        <button role="button" class="small-btn" @click="search()">搜索</button>
      </view>
      <view class="filter-row">
        <picker :range="scopes.map((item) => item.label)" @change="changeScope">
          <view class="filter-button">
            {{ scopes.find((item) => item.value === scope)?.label }}
            <uni-icons type="bottom" size="14" aria-hidden="true" />
          </view>
        </picker>
        <picker :range="['全部学科', ...subjects]" @change="changeSubject">
          <view class="filter-button">
            {{ subject || '全部学科' }}
            <uni-icons type="bottom" size="14" aria-hidden="true" />
          </view>
        </picker>
      </view>
      <view class="saved-ranges">
        <view v-if="ranges.length" class="saved-range-list">
          <view v-for="range in ranges" :key="range.id" class="saved-range">
            <button role="button" :disabled="saving" @click="applyRange(range)">
              {{ range.name }}
            </button>
            <button
              role="button"
              :aria-label="`移除复习范围：${range.name}`"
              :disabled="saving"
              @click="removeRange(range)"
            >
              ×
            </button>
          </view>
        </view>
        <button
          role="button"
          class="save-range-toggle"
          :aria-expanded="savingRange"
          @click="savingRange = !savingRange"
        >
          {{ savingRange ? '取消保存' : '保存当前复习范围' }}
        </button>
        <view v-if="savingRange" class="range-form">
          <input
            v-model="rangeName"
            aria-label="复习范围名称"
            placeholder="例如：一元一次方程"
            maxlength="40"
          />
          <button role="button" :disabled="saving || !rangeName.trim()" @click="saveRange">
            {{ saving ? '正在保存…' : '保存' }}
          </button>
        </view>
        <text v-if="rangeError" role="alert" class="range-error">{{ rangeError }}</text>
      </view>
      <state-panel
        v-if="loading || error"
        :state="error ? 'error' : 'loading'"
        :message="error"
        @retry="search(page)"
      />
      <template v-else>
        <view v-if="!items.length" class="empty-state">
          <text>
            {{ query || subject ? '没有找到符合条件的复习题' : '这个范围内还没有复习题' }}
          </text>
          <button
            v-if="query || subject || scope !== 'pending'"
            role="button"
            class="secondary-btn"
            @click="reset"
          >
            查看全部待复习
          </button>
          <button v-else role="button" class="secondary-btn" @click="go('/pages/problem/list')">
            查看错题
          </button>
        </view>
        <button
          v-for="item in items"
          :key="item.id"
          role="button"
          class="review-result"
          @click="open(item)"
        >
          <view class="result-meta">
            <text>{{ item.subject }} · {{ item.grade || '年级未设置' }}</text>
            <text>
              {{
                item.status === 'completed'
                  ? '已复习'
                  : item.is_due
                    ? '待复习'
                    : studyDate(item.due_at)
              }}
            </text>
          </view>
          <math-text class="question-preview" :text="item.question_text" />
          <view class="result-action">
            <text>{{ item.knowledge_points?.slice(0, 2).join(' · ') }}</text>
            <text>{{ item.status === 'pending' && item.is_due ? '开始复习' : '查看原题' }} ›</text>
          </view>
        </button>
        <view v-if="total > 20" class="pagination">
          <button role="button" :disabled="page === 1" @click="search(page - 1)">上一页</button>
          <text>{{ page }} / {{ Math.ceil(total / 20) }}</text>
          <button role="button" :disabled="page * 20 >= total" @click="search(page + 1)">
            下一页
          </button>
        </view>
      </template>
    </view>
  </view>
</template>
<script setup>
import { ref } from 'vue'
import { onLoad, onShow, onHide, onUnload } from '@dcloudio/uni-app'
import { getData, postData, deleteData } from '@/api/index.js'
import { CORE_SUBJECTS as subjects } from '@/constants/education.js'
import { go } from '@/utils/navigation.js'
import { studyDate } from '@/utils/learning.js'
const query = ref(''),
  subject = ref(''),
  scope = ref('pending'),
  items = ref([]),
  page = ref(1),
  total = ref(0),
  loading = ref(true),
  error = ref('')
const scopes = [
  { label: '全部待复习', value: 'pending' },
  { label: '今天到期', value: 'today' },
  { label: '已复习', value: 'completed' },
]
const ranges = ref([]),
  savingRange = ref(false),
  saving = ref(false),
  rangeName = ref(''),
  rangeError = ref('')
let revision = 0,
  active = false,
  rangeRevision = 0
async function search(target = 1) {
  const stamp = ++revision
  loading.value = true
  error.value = ''
  const token = uni.getStorageSync('minddimension_access_token')
  try {
    const result = await getData(
      `/reviews/search?q=${encodeURIComponent(query.value.trim())}&subject=${encodeURIComponent(subject.value)}&scope=${scope.value}&page=${target}`,
    )
    if (!active || stamp !== revision || token !== uni.getStorageSync('minddimension_access_token'))
      return
    items.value = result.items
    total.value = result.total
    page.value = result.page
  } catch (err) {
    if (stamp === revision) error.value = err.message || '复习题目暂时无法读取'
  } finally {
    if (stamp === revision) loading.value = false
  }
}
function changeScope(event) {
  scope.value = scopes[Number(event.detail.value)]?.value || 'pending'
  search()
}
function changeSubject(event) {
  subject.value = subjects[Number(event.detail.value) - 1] || ''
  search()
}
function reset() {
  query.value = subject.value = ''
  scope.value = 'pending'
  search()
}
async function loadRanges() {
  const stamp = ++rangeRevision,
    token = uni.getStorageSync('minddimension_access_token')
  try {
    const result = await getData('/reviews/filters')
    if (
      active &&
      stamp === rangeRevision &&
      token === uni.getStorageSync('minddimension_access_token')
    )
      ranges.value = result
  } catch (err) {
    if (active && stamp === rangeRevision) rangeError.value = err.message || '复习范围暂时无法读取'
  }
}
function applyRange(range) {
  query.value = range.q
  subject.value = range.subject
  scope.value = range.scope
  search()
}
async function saveRange() {
  if (saving.value || !rangeName.value.trim()) return
  const stamp = ++rangeRevision,
    token = uni.getStorageSync('minddimension_access_token')
  saving.value = true
  rangeError.value = ''
  try {
    const result = await postData('/reviews/filters', {
      name: rangeName.value.trim(),
      q: query.value.trim(),
      subject: subject.value,
      scope: scope.value,
    })
    if (
      !active ||
      stamp !== rangeRevision ||
      token !== uni.getStorageSync('minddimension_access_token')
    )
      return
    ranges.value = result
    savingRange.value = false
    rangeName.value = ''
  } catch (err) {
    if (active && stamp === rangeRevision)
      rangeError.value = err.message || '复习范围未能保存，请重试'
  } finally {
    if (stamp === rangeRevision) saving.value = false
  }
}
async function removeRange(range) {
  if (saving.value) return
  const stamp = ++rangeRevision,
    token = uni.getStorageSync('minddimension_access_token')
  saving.value = true
  rangeError.value = ''
  try {
    await deleteData(`/reviews/filters/${encodeURIComponent(range.id)}`)
    if (
      active &&
      stamp === rangeRevision &&
      token === uni.getStorageSync('minddimension_access_token')
    )
      ranges.value = ranges.value.filter((item) => item.id !== range.id)
  } catch (err) {
    if (active && stamp === rangeRevision)
      rangeError.value = err.message || '复习范围未能移除，请重试'
  } finally {
    if (stamp === rangeRevision) saving.value = false
  }
}
function open(item) {
  if (item.status === 'pending' && item.is_due)
    go(
      `/pages/review/review?plan=${encodeURIComponent(item.id)}&question=${encodeURIComponent(item.question_id)}`,
    )
  else go(`/pages/detail/detail?id=${encodeURIComponent(item.question_id)}`)
}
onLoad((params) => {
  query.value = params.q || ''
  subject.value = params.subject || ''
})
onShow(() => {
  active = true
  search(page.value)
  loadRanges()
})
function leave() {
  active = false
  revision++
  rangeRevision++
  items.value = []
  ranges.value = []
  saving.value = false
}
onHide(leave)
onUnload(leave)
</script>
<style scoped lang="scss">
.saved-ranges {
  margin: -4px 0 16px;
}
.saved-range-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.saved-range {
  display: flex;
  align-items: center;
  background: var(--color-surface);
  border-radius: 8px;
  max-width: 100%;
}
.saved-range button {
  margin: 0;
  padding: 8px 10px;
  min-height: 44px;
  background: transparent;
  font-size: 13px;
}
.saved-range button:first-child {
  min-width: 0;
  overflow-wrap: anywhere;
}
.saved-range button:last-child {
  flex-shrink: 0;
  min-width: 44px;
}
.save-range-toggle {
  margin: 0;
  padding: 8px 0;
  min-height: 44px;
  font-size: 13px;
  background: transparent;
  color: var(--color-text-secondary);
  text-align: left;
}
.range-form {
  display: flex;
  align-items: center;
  gap: 8px;
}
.range-form input {
  flex: 1;
  min-width: 0;
  min-height: 44px;
  padding: 8px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  font-size: 14px;
}
.range-form button {
  min-height: 44px;
  margin: 0;
  font-size: 14px;
  background: var(--color-primary-soft);
  color: var(--color-primary);
}
.range-error {
  font-size: 13px;
  color: var(--color-error);
}
.search-row,
.filter-row,
.result-meta,
.result-action,
.pagination {
  display: flex;
  align-items: center;
  gap: 10px;
}
.search-row {
  padding: 4px 8px 4px 14px;
  background: var(--color-surface);
  border-radius: 12px;
  border: 1px solid var(--color-border);
}
.search-row input {
  flex: 1;
  min-width: 0;
  min-height: 44px;
  font-size: 15px;
}
.search-row button {
  flex-shrink: 0;
  margin: 0;
}
.filter-row {
  flex-wrap: wrap;
  margin: 14px 0 20px;
}
.filter-button {
  min-height: 44px;
  padding: 10px 12px;
  background: var(--color-surface);
  border-radius: 8px;
  font-size: 14px;
}
.review-result {
  display: block;
  width: 100%;
  padding: 16px;
  margin: 0 0 12px;
  background: var(--color-surface);
  text-align: left;
  border-radius: 12px;
}
.result-meta {
  justify-content: space-between;
  font-size: 12px;
  color: var(--color-text-secondary);
  flex-wrap: wrap;
}
.question-preview {
  display: block;
  margin: 12px 0;
  font-size: 16px;
}
.result-action {
  justify-content: space-between;
  font-size: 13px;
}
.result-action > text:first-child {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--color-text-secondary);
}
.result-action > text:last-child {
  flex-shrink: 0;
  color: var(--color-primary);
}
.pagination {
  justify-content: space-between;
  font-size: 14px;
}
.pagination button {
  min-height: 44px;
  margin: 0;
  font-size: 14px;
  background: var(--color-surface);
}
.empty-state {
  padding: 32px 0;
  text-align: center;
}
.empty-state button {
  margin-top: 20px;
}
</style>
