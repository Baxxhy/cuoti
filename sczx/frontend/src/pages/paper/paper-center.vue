<template>
  <div class="page">
    <app-header title="错题组卷" back />
    <div class="page-content">
      <span v-if="selectionNotice" class="selection-notice">{{ selectionNotice }}</span>
      <div class="filter-card">
        <div class="field">
          <span class="field-label">学科</span>
          <WebPicker :range="['全部', ...subjects]" @change="setSubject">
            <div class="field-picker">{{ filter.subject || '全部' }}</div>
          </WebPicker>
        </div>
        <div
          class="filter-toggle"
          role="button"
          tabindex="0"
          :aria-expanded="showFilters"
          @click="showFilters = !showFilters"
          @keydown.enter="showFilters = !showFilters"
        >
          <span>更多筛选条件</span>
          <WebIcon
            aria-hidden="true"
            :type="showFilters ? 'top' : 'bottom'"
            size="22"
            color="var(--color-text-secondary)"
          />
        </div>
        <div v-show="showFilters" class="advanced-filters">
          <div class="field">
            <span class="field-label">知识点</span>
            <WebInput v-model="filter.knowledge_point" class="field-input" placeholder="可不填" />
          </div>
          <div class="field">
            <span class="field-label">错因类型</span>
            <WebPicker
              :range="errorLabels"
              @change="filter.error_type = errorCodes[$event.detail.value]"
            >
              <div class="field-picker">
                {{ filter.error_type ? errorTypeLabel(filter.error_type) : '全部错因' }}
              </div>
            </WebPicker>
          </div>
          <div class="range-filter">
            <div>
              <span>掌握度范围</span>
              <b>
                {{ Math.round(filter.mastery_min * 100) }}%—{{
                  Math.round(filter.mastery_max * 100)
                }}%
              </b>
            </div>
            <span>最低掌握度</span>
            <WebSlider
              :value="filter.mastery_min * 100"
              min="0"
              :max="filter.mastery_max * 100"
              activeColor="var(--color-primary)"
              @changing="filter.mastery_min = $event.detail.value / 100"
            />
            <span>最高掌握度</span>
            <WebSlider
              :value="filter.mastery_max * 100"
              :min="filter.mastery_min * 100"
              max="100"
              activeColor="var(--color-primary)"
              @changing="filter.mastery_max = $event.detail.value / 100"
            />
          </div>
          <div class="due-toggle" @click="filter.due_review = !filter.due_review">
            <div :class="{ on: filter.due_review }"><i /></div>
            <span>仅选择待复习题</span>
          </div>
        </div>
        <button role="button" class="secondary-btn" :disabled="searching" @click="search">
          {{ searching ? '正在筛选…' : '按条件筛选题目' }}
        </button>
      </div>
      <state-panel v-if="error" state="error" :message="error" @retry="load" />
      <state-panel v-else-if="searching" state="loading" />
      <div class="section-title">
        <span>选择题目（{{ selected.length }}）</span>
        <span class="section-link" @click="toggleAll">
          {{ selected.length === candidates.length ? '取消全选' : '全选' }}
        </span>
      </div>
      <div
        v-for="q in candidates"
        :key="q.id"
        class="candidate"
        :class="{ selected: selected.includes(q.id) }"
        @click="toggle(q.id)"
      >
        <div class="checkbox">
          <WebIcon
            aria-hidden="true"
            v-if="selected.includes(q.id)"
            type="checkmarkempty"
            size="24"
            color="#fff"
          />
        </div>
        <div class="list-main">
          <math-text class="list-title" :text="q.question_text || '待核对的题目'" inline />
          <math-text class="list-desc" :text="candidateDescription(q)" inline />
          <span class="list-meta">
            {{ errorTypeLabel(q.error_type) }}
          </span>
        </div>
      </div>
      <div v-if="!candidates.length && !searching && !error" class="empty">
        <span>当前筛选条件下没有可用错题</span>
      </div>
      <span v-if="actionError && !active" class="operation-error" role="alert">
        {{ actionError }}
      </span>
      <div class="field paper-name">
        <span class="field-label">试卷名称</span>
        <WebInput aria-label="新试卷名称" v-model="title" class="field-input" />
      </div>
      <button
        role="button"
        class="primary-btn"
        :disabled="!selected.length || busy || !!openingPaper"
        @click="create"
      >
        {{ busy && !active ? '正在创建…' : `创建试卷（${selected.length}题）` }}
      </button>
      <div class="section-title"><span>组卷历史</span></div>
      <span v-if="openingPaper" class="operation-status" role="status">正在打开试卷…</span>
      <span v-if="openError" class="operation-error" role="alert">{{ openError }}</span>
      <div
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
        <div class="paper-icon">
          <WebIcon aria-hidden="true" type="map-filled" size="24" color="var(--color-primary)" />
        </div>
        <div class="list-main">
          <math-text class="list-title" :text="paper.title" inline />
        </div>
        <WebIcon aria-hidden="true" type="right" size="24" color="var(--color-border)" />
      </div>
      <div v-if="active" class="paper-editor">
        <div class="editor-title">
          <component
            :is="'input'"
            class="paper-title-input"
            :value="active.title"
            aria-label="当前试卷名称"
            :disabled="busy || !!openingPaper"
            @input="active.title = $event.target.value"
          />
          <button
            role="button"
            class="delete-paper"
            :disabled="busy || !!openingPaper"
            @click="remove"
          >
            删除
          </button>
        </div>
        <span v-if="actionError" class="operation-error" role="alert">{{ actionError }}</span>
        <div v-for="(item, index) in active.items" :key="item.id" class="paper-item">
          <span class="item-index">{{ index + 1 }}</span>
          <div class="list-main">
            <b><math-text :text="item.question?.question_text" inline /></b>
            <div class="score-edit">
              <span class="score-label">分值</span>
              <div class="score-field">
                <component
                  :is="'input'"
                  class="paper-score-input"
                  :value="item.score"
                  :aria-label="`第${index + 1}题分值`"
                  :disabled="busy || !!openingPaper"
                  type="number"
                  min="1"
                  max="100"
                  inputmode="numeric"
                  @input="item.score = $event.target.value"
                />
              </div>
              <span class="score-unit">分</span>
            </div>
            <span v-if="item.analysis_ready === false" class="analysis-pending">
              答案与解析待补齐
            </span>
            <button
              role="button"
              v-if="item.question?.confirmed === false"
              class="analysis-link"
              :disabled="busy"
              @click="reviewQuestion(item)"
            >
              先核对题目
            </button>
          </div>
          <div class="sort">
            <button
              role="button"
              :disabled="index === 0 || busy || !!openingPaper"
              :aria-label="`第${index + 1}题上移`"
              @click="move(index, -1)"
            >
              ↑
            </button>
            <button
              role="button"
              :disabled="index === active.items.length - 1 || busy || !!openingPaper"
              :aria-label="`第${index + 1}题下移`"
              @click="move(index, 1)"
            >
              ↓
            </button>
          </div>
        </div>
        <div class="total-score">
          总分
          <b>{{ totalScore }}</b>
          分
        </div>
        <button
          role="button"
          class="secondary-btn"
          :disabled="busy || !!openingPaper"
          @click="save"
        >
          保存名称、排序与分值
        </button>
        <span v-if="exportProgress" class="operation-status" role="status">
          {{ exportProgress }}
        </span>
        <div class="export-grid">
          <button role="button" :disabled="busy || !!openingPaper" @click="exportFile('question')">
            题目 PDF
          </button>
          <button role="button" :disabled="busy || !!openingPaper" @click="exportFile('answer')">
            {{ missingAnalysis.length ? '补齐解析并导出答案' : '答案 PDF' }}
          </button>
          <button role="button" :disabled="busy || !!openingPaper" @click="exportFile('excel')">
            学习表格
          </button>
        </div>
        <div
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
          <WebIcon
            aria-hidden="true"
            type="download-filled"
            size="24"
            color="var(--color-primary)"
          />
          <span>{{ exportLabel[file.kind] || '导出文件' }}</span>
          <small>{{ openingExport === file.id ? '准备中…' : '打开' }}</small>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { browser } from '@/platform/browser.js'
import MathText from '@/components/math-text/math-text.vue'
import { computed, reactive, ref } from 'vue'
import { onLoad, onUnload } from '@/platform/lifecycle.js'
import { go } from '@/utils/navigation.js'
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
const exportProgress = ref('')
const missingAnalysis = computed(() =>
  (active.value?.items || []).filter((item) => item.analysis_ready === false),
)
function candidateDescription(question) {
  const points = (Array.isArray(question.knowledge_points) ? question.knowledge_points : []).filter(
    (value) =>
      typeof value === 'string' &&
      value.trim() &&
      !['null', 'undefined'].includes(value.trim().toLowerCase()),
  )
  return `${question.subject || '学科待确认'} · ${points.length ? points.join('、') : '知识点待分析'}`
}
async function reviewQuestion(item) {
  if (busy.value || openingPaper.value) return
  busy.value = true
  try {
    await persistEditor()
    go(`/pages/ocr/ocr?id=${encodeURIComponent(item.question_id)}`)
  } catch (error) {
    actionError.value = error.message || '试卷未保存，请重试。'
  } finally {
    busy.value = false
  }
}
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
    browser.showToast({ title: '试卷已保存', icon: 'success' })
  } catch (err) {
    actionError.value = err.message || '保存未完成，当前编辑内容仍在，请重试。'
  } finally {
    busy.value = false
  }
}

async function remove() {
  if (busy.value || openingPaper.value || !active.value) return
  const id = active.value.id
  browser.showModal({
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
    if (kind === 'answer' && missingAnalysis.value.length) {
      const pending = [...missingAnalysis.value]
      for (let index = 0; index < pending.length; index++) {
        const item = pending[index]
        const number =
          active.value.items.findIndex((row) => row.question_id === item.question_id) + 1
        if (item.question?.confirmed === false)
          throw new Error(`第${number}题尚未核对，请先点“先核对题目”，确认后再补齐解析。`)
        exportProgress.value = `正在补齐第${number}题的解析与知识点（${index + 1}/${pending.length}）…`
        await postData(
          `/questions/${item.question_id}/analyze`,
          {},
          { timeout: 180000, silent: true },
        )
        if (disposed) return
      }
      active.value = await getData(`/papers/${active.value.id}`, { silent: true })
      if (missingAnalysis.value.length)
        throw new Error('部分题目的分析仍不完整，请核对原题后重试；本次未生成答案 PDF。')
      await search()
    }
    if (disposed) return
    exportProgress.value = kind === 'excel' ? '正在生成学习表格…' : '正在排版 PDF…'
    await postData(`/papers/${active.value.id}/export`, { kind })
    if (await open(active.value.id, true)) browser.showToast({ title: '导出已生成', icon: 'success' })
  } catch (err) {
    actionError.value = err.message || '导出未完成，可以重试；已保存的试卷不受影响。'
  } finally {
    exportProgress.value = ''
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
    browser.showToast({ title: error.message || '文件暂时无法打开，请重试', icon: 'none' })
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
.filter-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 12px;
  align-items: end;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--color-border);
}
.filter-card > .field {
  margin: 0;
}
.filter-card .filter-toggle {
  margin: 0;
  justify-content: flex-end;
  gap: 8px;
}
.filter-card > .secondary-btn,
.advanced-filters {
  grid-column: 1 / -1;
  margin: 0;
}
.candidate .list-desc {
  max-height: 3.2em;
  overflow: hidden;
  font-size: 13px;
  line-height: 1.6;
}
.paper-name {
  margin-top: 20px;
}

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
  margin-top: 11.0px;
  padding: 10.0px;
  background: var(--color-bg);
  border-radius: 9.0px;
}
.range-filter > div {
  display: flex;
  justify-content: space-between;
}
.range-filter > div b {
  color: var(--color-primary);
}
.range-filter > span {
  font-size: 10.5px;
  color: var(--color-text-secondary);
}
.range-filter slider {
  margin: 1.5px 0;
}
.due-toggle {
  display: flex;
  align-items: center;
  gap: 7.0px;
  margin-top: 12.0px;
}
.due-toggle > div {
  width: 38.0px;
  height: 21.0px;
  padding: 2.5px;
  background: var(--color-border);
  border-radius: 15.0px;
}
.due-toggle > div.on {
  background: var(--color-primary);
}
.due-toggle i {
  display: block;
  width: 16.0px;
  height: 16.0px;
  border-radius: 50%;
  background: #fff;
  transition: 0.2s;
}
.due-toggle .on i {
  transform: translateX(17.0px);
}
.candidate {
  display: flex;
  gap: 9.0px;
  padding: 12.5px;
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
  width: 21.0px;
  height: 21.0px;
  flex: none;
  border: 1.0px solid var(--color-border);
  border-radius: 5.0px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.selected .checkbox {
  background: var(--color-primary);
  border-color: var(--color-primary);
}
.paper-icon {
  width: 35.0px;
  height: 35.0px;
  border-radius: 9.0px;
  background: var(--color-bg);
  display: flex;
  align-items: center;
  justify-content: center;
}
.paper-editor {
  margin-top: 12.5px;
  padding: 14.0px;
  border-radius: 10px;
  border: 1px solid var(--color-border);
  background: #fff;
}
.editor-title {
  display: flex;
  gap: 7.5px;
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
.editor-title :deep(.paper-title-input:focus),
.score-field:focus-within {
  border-color: var(--color-primary);
  outline: none;
  box-shadow: none;
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
  gap: 6.0px;
  padding: 10.0px 0;
  border-bottom: 1px solid var(--color-border);
}
.item-index {
  width: 21.0px;
  height: 21.0px;
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
  gap: 6px;
  margin-top: 4px;
  color: var(--color-text-secondary);
  font-size: 13px;
}
.score-label,
.score-unit {
  flex: none;
}
.score-field {
  display: flex;
  align-items: center;
  border-bottom: 1px solid var(--color-border);
}
.score-edit :deep(.paper-score-input) {
  box-sizing: border-box;
  flex: none;
  width: 44px;
  height: 36px;
  min-height: 36px;
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  font-size: 14px;
  font-weight: 400;
  font-variant-numeric: tabular-nums;
  line-height: 36px;
  text-align: center;
  color: var(--color-text-primary);
  appearance: textfield;
  -moz-appearance: textfield;
}
.score-edit :deep(.paper-score-input::-webkit-inner-spin-button),
.score-edit :deep(.paper-score-input::-webkit-outer-spin-button) {
  margin: 0;
  -webkit-appearance: none;
}
.analysis-pending {
  display: block;
  margin-top: 8px;
  color: #96701b;
  font-size: 12px;
}
.analysis-link {
  width: auto;
  margin: 8px 0 0;
  padding: 4px 8px;
  font-size: 13px;
  color: var(--color-primary);
  background: var(--color-primary-soft);
}
.sort {
  display: flex;
  flex-direction: column;
  gap: 8px;
  color: var(--color-primary);
  font-size: 15.0px;
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
  margin-top: 9.0px;
  color: var(--color-text-secondary);
}
.total-score b {
  font-size: 16.0px;
  color: var(--color-primary);
}
.export-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 110px), 1fr));
  gap: 5.0px;
  margin-top: 10.0px;
}
.export-grid button {
  min-width: 0;
  min-height: 44px;
  padding: 9.0px 2.5px;
  margin: 0;
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-size: 14px;
  line-height: 1.6;
  border-radius: 7.0px;
}
.download-row {
  display: flex;
  align-items: center;
  gap: 6.5px;
  margin-top: 8.0px;
  padding: 9.0px;
  background: var(--color-bg);
  border-radius: 7.5px;
}
.download-row span {
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
