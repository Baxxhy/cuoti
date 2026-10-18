<template>
  <view class="page">
    <app-header title="错题组卷" subtitle="选择题目，整理练习与导出" back />
    <view class="page-content">
      <text v-if="selectionNotice" class="selection-notice">{{ selectionNotice }}</text>
      <view class="card filter-card">
        <view class="field">
          <text class="field-label">试卷名称</text>
          <input v-model="title" class="field-input" />
        </view>
        <view class="field">
          <text class="field-label">学科</text>
          <picker :range="['全部', ...subjects]" @change="setSubject">
            <view class="field-picker">{{ filter.subject || '全部' }}</view>
          </picker>
        </view>
        <view
          class="filter-toggle"
          role="button"
          tabindex="0"
          :aria-expanded="showFilters"
          @click="showFilters = !showFilters"
          @keydown.enter="showFilters = !showFilters"
        >
          <text>更多筛选条件</text>
          <uni-icons
            :type="showFilters ? 'top' : 'bottom'"
            size="22"
            color="var(--color-text-secondary)"
          />
        </view>
        <view v-show="showFilters" class="advanced-filters">
          <view class="field">
            <text class="field-label">知识点</text>
            <input v-model="filter.knowledge_point" class="field-input" placeholder="可不填" />
          </view>
          <view class="field">
            <text class="field-label">错因类型</text>
            <picker
              :range="errorLabels"
              @change="filter.error_type = errorCodes[$event.detail.value]"
            >
              <view class="field-picker">
                {{ filter.error_type ? errorTypeLabel(filter.error_type) : '全部错因' }}
              </view>
            </picker>
          </view>
          <view class="range-filter">
            <view>
              <text>掌握度范围</text>
              <b>
                {{ Math.round(filter.mastery_min * 100) }}%—{{
                  Math.round(filter.mastery_max * 100)
                }}%
              </b>
            </view>
            <text>最低掌握度</text>
            <slider
              :value="filter.mastery_min * 100"
              min="0"
              :max="filter.mastery_max * 100"
              activeColor="var(--color-primary)"
              @changing="filter.mastery_min = $event.detail.value / 100"
            />
            <text>最高掌握度</text>
            <slider
              :value="filter.mastery_max * 100"
              :min="filter.mastery_min * 100"
              max="100"
              activeColor="var(--color-primary)"
              @changing="filter.mastery_max = $event.detail.value / 100"
            />
          </view>
          <view class="due-toggle" @click="filter.due_review = !filter.due_review">
            <view :class="{ on: filter.due_review }"><i /></view>
            <text>仅选择待复习题</text>
          </view>
        </view>
        <button class="secondary-btn" :disabled="searching" @click="search">
          {{ searching ? '正在筛选…' : '按条件筛选题目' }}
        </button>
      </view>
      <state-panel v-if="error" state="error" :message="error" @retry="load" />
      <state-panel v-else-if="searching" state="loading" />
      <view class="section-title">
        <text>选择题目（{{ selected.length }}）</text>
        <text class="section-link" @click="toggleAll">
          {{ selected.length === candidates.length ? '取消全选' : '全选' }}
        </text>
      </view>
      <view
        v-for="q in candidates"
        :key="q.id"
        class="candidate"
        :class="{ selected: selected.includes(q.id) }"
        @click="toggle(q.id)"
      >
        <view class="checkbox">
          <uni-icons v-if="selected.includes(q.id)" type="checkmarkempty" size="24" color="#fff" />
        </view>
        <view class="list-main">
          <text class="list-title">{{ q.question_text || q.title }}</text>
          <text class="list-desc">
            {{ q.subject }} · {{ (q.knowledge_points || []).join('、') || q.grade }}
          </text>
          <text class="list-meta">
            掌握 {{ Math.round((q.mastery_score || 0) * 100) }}% ·
            {{ errorTypeLabel(q.error_type) }}
          </text>
        </view>
      </view>
      <view v-if="!candidates.length && !searching && !error" class="empty">
        <text>当前筛选条件下没有可用错题</text>
      </view>
      <text v-if="actionError && !active" class="operation-error" role="alert">
        {{ actionError }}
      </text>
      <button
        class="primary-btn"
        :disabled="!selected.length || busy || !!openingPaper"
        @click="create"
      >
        {{ busy && !active ? '正在创建…' : `创建试卷（${selected.length}题）` }}
      </button>
      <view class="section-title"><text>组卷历史</text></view>
      <text v-if="openingPaper" class="operation-status" role="status">正在打开试卷…</text>
      <text v-if="openError" class="operation-error" role="alert">{{ openError }}</text>
      <view
        v-for="paper in papers"
        :key="paper.id"
        class="list-card history-paper"
        role="button"
        tabindex="0"
        :aria-pressed="active?.id === paper.id"
        :aria-disabled="busy"
        @click="open(paper.id)"
        @keydown.enter="open(paper.id)"
        @keydown.space.prevent="open(paper.id)"
      >
        <view class="paper-icon">
          <uni-icons type="map-filled" size="24" color="var(--color-primary)" />
        </view>
        <view class="list-main">
          <text class="list-title">{{ paper.title }}</text>
          <text class="list-desc">点击查看、调整分值、排序与导出</text>
        </view>
        <uni-icons type="right" size="24" color="var(--color-border)" />
      </view>
      <view v-if="active" class="paper-editor">
        <view class="editor-title">
          <!-- #ifdef H5 -->
          <component
            :is="'input'"
            class="paper-title-input"
            :value="active.title"
            aria-label="当前试卷名称"
            :disabled="busy || !!openingPaper"
            @input="active.title = $event.target.value"
          />
          <!-- #endif -->
          <!-- #ifndef H5 -->
          <input
            v-model="active.title"
            class="paper-title-input"
            aria-label="当前试卷名称"
            :disabled="busy || !!openingPaper"
          />
          <!-- #endif -->
          <button class="delete-paper" :disabled="busy || !!openingPaper" @click="remove">
            删除
          </button>
        </view>
        <text v-if="actionError" class="operation-error" role="alert">{{ actionError }}</text>
        <view v-for="(item, index) in active.items" :key="item.id" class="paper-item">
          <text class="item-index">{{ index + 1 }}</text>
          <view class="list-main">
            <b>{{ item.question?.question_text }}</b>
            <view class="score-edit">
              <text>分值</text>
              <!-- #ifdef H5 -->
              <component
                :is="'input'"
                class="paper-score-input"
                :value="item.score"
                :aria-label="`第${index + 1}题分值`"
                :disabled="busy || !!openingPaper"
                type="number"
                min="1"
                max="100"
                @input="item.score = $event.target.value"
              />
              <!-- #endif -->
              <!-- #ifndef H5 -->
              <input
                v-model.number="item.score"
                class="paper-score-input"
                :aria-label="`第${index + 1}题分值`"
                :disabled="busy || !!openingPaper"
                type="number"
                min="1"
                max="100"
              />
              <!-- #endif -->
              <text>分</text>
            </view>
          </view>
          <view class="sort">
            <button
              :disabled="index === 0 || busy || !!openingPaper"
              :aria-label="`第${index + 1}题上移`"
              @click="move(index, -1)"
            >
              ↑
            </button>
            <button
              :disabled="index === active.items.length - 1 || busy || !!openingPaper"
              :aria-label="`第${index + 1}题下移`"
              @click="move(index, 1)"
            >
              ↓
            </button>
          </view>
        </view>
        <view class="total-score">
          总分
          <b>{{ totalScore }}</b>
          分
        </view>
        <button class="secondary-btn" :disabled="busy || !!openingPaper" @click="save">
          保存名称、排序与分值
        </button>
        <view class="export-grid">
          <button :disabled="busy || !!openingPaper" @click="exportFile('question')">
            题目 PDF
          </button>
          <button :disabled="busy || !!openingPaper" @click="exportFile('answer')">答案 PDF</button>
          <button :disabled="busy || !!openingPaper" @click="exportFile('excel')">学习表格</button>
        </view>
        <view
          v-for="file in active.exports"
          :key="file.id"
          class="download-row"
          role="button"
          tabindex="0"
          :aria-disabled="busy || !!openingPaper || !!openingExport"
          @click="openFile(file.id)"
          @keydown.enter="openFile(file.id)"
          @keydown.space.prevent="openFile(file.id)"
        >
          <uni-icons type="download-filled" size="24" color="var(--color-primary)" />
          <text>{{ exportLabel[file.kind] || '导出文件' }}</text>
          <small>{{ openingExport === file.id ? '准备中…' : '打开' }}</small>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { onLoad, onUnload } from '@dcloudio/uni-app'
import { openExportFile } from '@/utils/export-file.js'
import { deleteData, getData, patchData, postData } from '@/api/index.js'
import {
  CORE_SUBJECTS as subjects,
  ERROR_TYPE_LABELS,
  errorTypeLabel,
} from '@/constants/education.js'
const showFilters = ref(false)
const initialSelection = ref(null)
const selectionNotice = ref('')
const actionError = ref(''),
  openError = ref(''),
  openingPaper = ref('')
let openVersion = 0,
  disposed = false
const error = ref(''),
  errorCodes = ['', ...Object.keys(ERROR_TYPE_LABELS)],
  errorLabels = ['全部错因', ...Object.values(ERROR_TYPE_LABELS)]
const candidates = ref([]),
  papers = ref([]),
  selected = ref([]),
  active = ref(null),
  title = ref('薄弱点专项练习'),
  busy = ref(false),
  openingExport = ref(''),
  searching = ref(false)
const filter = reactive({
  subject: '',
  knowledge_point: '',
  error_type: '',
  mastery_min: 0,
  mastery_max: 1,
  due_review: false,
})
const exportLabel = { question: '题目 PDF', answer: '答案解析 PDF', excel: '学习数据表' },
  totalScore = computed(
    () => active.value?.items?.reduce((sum, item) => sum + Number(item.score || 0), 0) || 0,
  )
async function load() {
  error.value = ''
  try {
    papers.value = await getData('/papers')
    await search()
  } catch (err) {
    error.value = err.message || '组卷记录暂时无法加载，请重试'
  }
}
function setSubject(e) {
  filter.subject = e.detail.value ? subjects[e.detail.value - 1] : ''
}
async function search() {
  if (searching.value) return
  searching.value = true
  error.value = ''
  try {
    const params = Object.entries(filter)
      .filter(([, value]) => value !== '' && value !== false)
      .map(([key, value]) => `${key}=${encodeURIComponent(value)}`)
      .join('&')
    candidates.value = await getData(`/papers/candidates?${params}`)
    if (initialSelection.value) {
      const requested = initialSelection.value
      selected.value = requested.filter((id) => candidates.value.some((q) => q.id === id))
      selectionNotice.value = `已带入 ${selected.value.length} 道题，可继续添加。${selected.value.length < requested.length ? '部分题目不符合组卷条件，请核对后再创建。' : ''}`
      initialSelection.value = null
    } else selected.value = selected.value.filter((id) => candidates.value.some((q) => q.id === id))
  } catch (err) {
    error.value = err.message || '筛选未完成，请重试'
  } finally {
    searching.value = false
  }
}
function toggle(id) {
  selected.value = selected.value.includes(id)
    ? selected.value.filter((x) => x !== id)
    : [...selected.value, id]
}
function toggleAll() {
  selected.value =
    selected.value.length === candidates.value.length ? [] : candidates.value.map((x) => x.id)
}
async function create() {
  if (busy.value || openingPaper.value || !selected.value.length) return
  busy.value = true
  actionError.value = ''
  try {
    const paper = await postData('/papers', {
      title: title.value,
      question_ids: selected.value,
      items: selected.value.map((question_id) => ({ question_id, score: 10 })),
      filters: { ...filter },
    })
    await open(paper.id, true)
    papers.value = await getData('/papers')
  } catch (err) {
    actionError.value = err.message || '未能完成创建，请先查看组卷历史，再决定是否重试。'
  } finally {
    busy.value = false
  }
}
async function open(id, internal = false) {
  if (disposed || (busy.value && !internal)) return false
  const version = ++openVersion
  openingPaper.value = id
  openError.value = ''
  try {
    const paper = await getData(`/papers/${id}`, { silent: true })
    if (disposed || version !== openVersion) return false
    active.value = paper
    actionError.value = ''
    return true
  } catch (err) {
    if (!disposed && version === openVersion)
      openError.value = `${err.message || '试卷暂时无法打开'}，可重新选择这份试卷。`
    return false
  } finally {
    if (!disposed && version === openVersion) openingPaper.value = ''
  }
}
function move(index, delta) {
  if (busy.value || openingPaper.value || !active.value) return
  const target = index + delta
  if (target < 0 || target >= active.value.items.length) return
  const [item] = active.value.items.splice(index, 1)
  active.value.items.splice(target, 0, item)
}
async function persistEditor() {
  active.value = await patchData(`/papers/${active.value.id}`, {
    title: active.value.title,
    items: active.value.items.map((item) => ({
      question_id: item.question_id,
      score: Math.max(1, Math.min(100, Number(item.score) || 10)),
    })),
  })
  papers.value = await getData('/papers')
}
async function save() {
  if (busy.value || openingPaper.value || !active.value) return
  busy.value = true
  actionError.value = ''
  try {
    await persistEditor()
    uni.showToast({ title: '试卷已保存', icon: 'success' })
  } catch (err) {
    actionError.value = err.message || '保存未完成，当前编辑内容仍在，请重试。'
  } finally {
    busy.value = false
  }
}

async function remove() {
  if (busy.value || openingPaper.value || !active.value) return
  const id = active.value.id
  uni.showModal({
    confirmText: '确定',
    cancelText: '取消',
    title: '删除试卷',
    content: '确定删除这份试卷及导出记录吗？',
    success: async (r) => {
      if (r.confirm && active.value?.id === id && !busy.value && !openingPaper.value && !disposed) {
        busy.value = true
        actionError.value = ''
        try {
          await deleteData(`/papers/${id}`)
          active.value = null
          papers.value = papers.value.filter((paper) => paper.id !== id)
        } catch (err) {
          actionError.value = err.message || '删除未完成，试卷仍保留，可以重试。'
        } finally {
          busy.value = false
        }
      }
    },
  })
}
async function exportFile(kind) {
  if (busy.value || openingPaper.value || !active.value) return
  busy.value = true
  actionError.value = ''
  try {
    await persistEditor()
    await postData(`/papers/${active.value.id}/export`, { kind })
    if (await open(active.value.id, true)) uni.showToast({ title: '导出已生成', icon: 'success' })
  } catch (err) {
    actionError.value = err.message || '导出未完成，可以重试；已保存的试卷不受影响。'
  } finally {
    busy.value = false
  }
}
async function openFile(exportId) {
  if (busy.value || openingPaper.value || openingExport.value || !active.value) return
  const paperId = active.value.id
  openingExport.value = exportId
  try {
    await openExportFile(async () => {
      const paper = await getData(`/papers/${paperId}`, { silent: true })
      const file = paper.exports.find((item) => item.id === exportId)
      if (!file?.url) throw new Error('文件已不存在，请重新生成导出')
      // Refresh only the file link; unsaved title, scores and sorting stay intact.
      return file.url
    })
  } catch (error) {
    uni.showToast({ title: error.message || '文件暂时无法打开，请重试', icon: 'none' })
  } finally {
    openingExport.value = ''
  }
}

onLoad((q) => {
  filter.subject = subjects.includes(q.subject) ? q.subject : ''
  filter.knowledge_point = q.knowledge || ''
  if (q.ids)
    initialSelection.value = [...new Set(String(q.ids).split(',').filter(Boolean))].slice(0, 50)
  load()
})
onUnload(() => {
  disposed = true
  openVersion++
})
</script>

<style scoped lang="scss">
.filter-card > .field:first-child {
  margin-top: 0;
}
.filter-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 44px;
  margin-top: 12px;
  color: var(--color-text-secondary);
  font-size: 13px;
}
.advanced-filters {
  border-top: 1px solid var(--color-border);
  padding-top: 4px;
}
.range-filter {
  margin-top: 22rpx;
  padding: 20rpx;
  background: var(--color-bg);
  border-radius: 18rpx;
}
.range-filter > view {
  display: flex;
  justify-content: space-between;
}
.range-filter > view b {
  color: var(--color-primary);
}
.range-filter > text {
  font-size: 21rpx;
  color: var(--color-text-secondary);
}
.range-filter slider {
  margin: 3rpx 0;
}
.due-toggle {
  display: flex;
  align-items: center;
  gap: 14rpx;
  margin-top: 24rpx;
}
.due-toggle > view {
  width: 76rpx;
  height: 42rpx;
  padding: 5rpx;
  background: var(--color-border);
  border-radius: 30rpx;
}
.due-toggle > view.on {
  background: var(--color-primary);
}
.due-toggle i {
  display: block;
  width: 32rpx;
  height: 32rpx;
  border-radius: 50%;
  background: #fff;
  transition: 0.2s;
}
.due-toggle .on i {
  transform: translateX(34rpx);
}
.candidate {
  display: flex;
  gap: 18rpx;
  padding: 25rpx;
  background: #fff;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  margin-bottom: 10px;
}
.candidate.selected {
  border-color: var(--color-primary);
  background: var(--color-primary-soft);
}
.checkbox {
  width: 42rpx;
  height: 42rpx;
  flex: none;
  border: 2rpx solid var(--color-border);
  border-radius: 10rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}
.selected .checkbox {
  background: var(--color-primary);
  border-color: var(--color-primary);
}
.paper-icon {
  width: 70rpx;
  height: 70rpx;
  border-radius: 18rpx;
  background: var(--color-bg);
  display: flex;
  align-items: center;
  justify-content: center;
}
.paper-editor {
  margin-top: 25rpx;
  padding: 28rpx;
  border-radius: 10px;
  border: 1px solid var(--color-border);
  background: #fff;
}
.editor-title {
  display: flex;
  gap: 15rpx;
  align-items: center;
}
.editor-title :deep(.paper-title-input) {
  flex: 1;
  width: 0;
  min-width: 0;
  min-height: 44px;
  height: auto;
  box-sizing: border-box;
  padding: 10px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-bg);
  color: var(--color-text-primary);
  font-size: 16px;
  line-height: 1.5;
  font-weight: 700;
}
.delete-paper {
  flex: none;
  min-width: 44px;
  min-height: 44px;
  margin: 0;
  padding: 0 8px;
  background: transparent;
  color: var(--color-error);
  font-size: 14px;
}
.delete-paper::after,
.sort button::after {
  border: none;
}
.paper-item {
  display: grid;
  grid-template-columns: 24px minmax(0, 1fr) 44px;
  gap: 12rpx;
  padding: 20rpx 0;
  border-bottom: 1px solid var(--color-border);
}
.item-index {
  width: 42rpx;
  height: 42rpx;
  border-radius: 50%;
  background: var(--color-primary-soft);
  color: var(--color-primary);
  display: flex;
  align-items: center;
  justify-content: center;
}
.paper-item b {
  font-size: 14px;
  line-height: 1.65;
  overflow-wrap: anywhere;
}
.score-edit {
  display: flex;
  align-items: center;
  gap: 8rpx;
  color: var(--color-text-secondary);
  font-size: 13px;
  margin-top: 9rpx;
}
.score-edit :deep(.paper-score-input) {
  box-sizing: border-box;
  min-height: 44px;
  width: 64px;
  padding: 6px;
  border: 1px solid var(--color-border);
  font-size: 16px;
  line-height: 1.5;
  text-align: center;
  border-radius: 10rpx;
  background: var(--color-bg);
  color: var(--color-text-primary);
}
.sort {
  display: flex;
  flex-direction: column;
  gap: 8px;
  color: var(--color-primary);
  font-size: 30rpx;
}
.sort button {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  min-height: 44px;
  margin: 0;
  padding: 0;
  color: var(--color-primary);
  background: var(--color-primary-soft);
  font-size: 18px;
  border-radius: 8px;
}
.sort button[disabled] {
  opacity: 0.4;
}
.history-paper[aria-pressed='true'] {
  border-color: var(--color-primary);
}
.history-paper[aria-disabled='true'] {
  opacity: 0.6;
}
.operation-error,
.operation-status {
  display: block;
  margin: 12px 0;
  font-size: 14px;
  line-height: 1.65;
  overflow-wrap: anywhere;
}
.operation-error {
  color: var(--color-error);
}
.operation-status {
  color: var(--color-text-secondary);
}
.total-score {
  text-align: right;
  margin-top: 18rpx;
  color: var(--color-text-secondary);
}
.total-score b {
  font-size: 32rpx;
  color: var(--color-primary);
}
.export-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 110px), 1fr));
  gap: 10rpx;
  margin-top: 20rpx;
}
.export-grid button {
  min-width: 0;
  min-height: 44px;
  padding: 18rpx 5rpx;
  margin: 0;
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-size: 14px;
  line-height: 1.6;
  border-radius: 14rpx;
}
.download-row {
  display: flex;
  align-items: center;
  gap: 13rpx;
  margin-top: 16rpx;
  padding: 18rpx;
  background: var(--color-bg);
  border-radius: 15rpx;
}
.download-row text {
  flex: 1;
}
.download-row small {
  color: var(--color-primary);
}

.selection-notice {
  display: block;
  margin-bottom: 12px;
  color: var(--color-text-secondary);
  font-size: 14px;
  line-height: 1.6;
}
</style>
