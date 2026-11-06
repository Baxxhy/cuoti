<template>
  <div class="page report-page">
    <app-header :title="relationsMode ? '知识关系' : '学习报告'" back />
    <div class="page-content">
      <state-panel
        v-if="loading || error"
        :state="error ? 'error' : 'loading'"
        :message="error"
        @retry="load"
      />
      <template v-else>
        <template v-if="!relationsMode">
          <div
            v-if="!progressItem && !attentionItem && !stableItem && !trend.length"
            class="report-empty"
          >
            <span class="empty-title">还没有学习报告</span>
            <button
              tabindex="0"
              role="button"
              class="small-btn"
              @click="go('/pages/problem/list')"
              @keydown.enter.prevent="go('/pages/problem/list')"
              @keydown.space.prevent
              @keyup.space.prevent="go('/pages/problem/list')"
            >
              查看我的错题
            </button>
          </div>
          <div v-if="progressItem" class="report-block progress-block">
            <span class="block-label">{{ progressItem.subject }} · 近期学习</span>
            <template v-if="progressItem">
              <math-text class="block-title" :text="progressItem.knowledge_point" inline />
              <div class="change-line">
                <b>{{ Math.round(progressItem.mastery_score * 100) }}%</b>
                <span>学习记录估计</span>
              </div>
              <span class="block-detail"></span>
              <button
                class="primary-btn"
                role="button"
                @click="go(scopedQuestionURL({ subject: progressItem.subject || '' }))"
              >
                查看{{ progressItem.subject }}错题
              </button>
            </template>
            <span v-else class="muted">完成学习后，这里会显示实际掌握记录。</span>
          </div>

          <div v-if="attentionItem" class="report-block attention-block">
            <span class="block-label">{{ attentionItem.subject }} · 最需要注意</span>
            <template v-if="attentionItem">
              <math-text class="block-title" :text="attentionItem.label" />
              <span class="block-detail"></span>
              <button
                tabindex="0"
                role="button"
                class="secondary-btn"
                @click="
                  go(
                    scopedQuestionURL({
                      subject: attentionItem.subject || '',
                      search: attentionItem.search,
                    }),
                  )
                "
                @keydown.enter.prevent="
                  go(
                    scopedQuestionURL({
                      subject: attentionItem.subject || '',
                      search: attentionItem.search,
                    }),
                  )
                "
                @keydown.space.prevent
                @keyup.space.prevent="
                  go(
                    scopedQuestionURL({
                      subject: attentionItem.subject || '',
                      search: attentionItem.search,
                    }),
                  )
                "
              >
                查看相关错题
              </button>
            </template>
            <span v-else class="muted">目前没有集中出现的错因。</span>
          </div>

          <div v-if="stableItem" class="report-block stable-block">
            <span class="block-label">{{ stableItem.subject }} · 正在稳定</span>
            <template v-if="stableItem">
              <math-text class="block-title" :text="stableItem.knowledge_point" inline />
              <span class="stable-score">
                学习记录估计 {{ Math.round(stableItem.mastery_score * 100) }}%
              </span>
              <span class="block-detail"></span>
            </template>
            <span v-else class="muted">掌握度达到较稳定状态后会显示在这里。</span>
          </div>

          <button
            tabindex="0"
            role="button"
            v-if="trend.length"
            class="record-toggle"
            :aria-expanded="showTrend"
            @click="toggleTrend"
            @keydown.enter.prevent="toggleTrend"
            @keydown.space.prevent
            @keyup.space.prevent="toggleTrend"
          >
            {{ showTrend ? '收起每日记录' : '查看每日记录' }}
          </button>
          <div v-if="trend.length && showTrend" class="trend-panel">
            <span class="muted">不同日期涉及的知识点可能不同。</span>
            <div class="trend-bars">
              <div v-for="point in trend" :key="point.date">
                <div :style="{ height: Math.max(4, point.score * 0.7) + 'px' }" />
                <span>{{ point.date?.slice(5) }}</span>
              </div>
            </div>
            <span v-if="!trend.length" class="muted">完成练习后显示趋势</span>
          </div>
        </template>
        <template v-if="relationsMode">
          <div class="relation-summary">
            <span v-if="graphLoaded">{{ graphSummary }}</span>
          </div>
          <WebScroll scroll-x class="filter-scroll">
            <div class="chip-row">
              <span
                v-for="value in ['全部', ...subjects]"
                :key="value"
                class="chip"
                :class="{ active: subject === (value === '全部' ? '' : value) }"
                @click="selectSubject(value)"
              >
                {{ value }}
              </span>
            </div>
          </WebScroll>
          <state-panel
            v-if="graphLoading || graphError"
            :state="graphError ? 'error' : 'loading'"
            :message="graphError"
            @retry="loadGraph"
          />
          <template v-else>
            <button
              tabindex="0"
              role="button"
              class="record-toggle"
              :aria-expanded="graphList"
              @click="graphList = !graphList"
              @keydown.enter.prevent="graphList = !graphList"
              @keydown.space.prevent
              @keyup.space.prevent="graphList = !graphList"
            >
              {{ graphList ? '用图查看' : '用列表查看' }}
            </button>
            <div v-if="graphList" class="graph-list">
              <button
                tabindex="0"
                role="button"
                v-for="node in graph.nodes"
                :key="node.id"
                class="graph-list-item"
                @click="selected = node"
                @keydown.enter.prevent="selected = node"
                @keydown.space.prevent
                @keyup.space.prevent="selected = node"
              >
                <math-text
                  :text="(categoryLabel[node.category] || '学习关系') + ' · ' + node.name"
                  inline
                />
              </button>
              <span v-if="!graph.nodes?.length" class="muted">还没有可查看的知识关系</span>
            </div>
            <cognition-canvas v-else :graph="graph" @select="selected = $event" />
          </template>
          <div v-if="selected" class="node-detail">
            <span class="tag">{{ categoryLabel[selected.category] || '学习关系' }}</span>
            <b><math-text :text="selected.name" inline /></b>
            <math-text :text="selected.detail || '来自你的错题学习记录'" inline />
            <button
              tabindex="0"
              role="button"
              v-if="selected.question_id"
              class="small-btn"
              @click="go(`/pages/detail/detail?id=${selected.question_id}`)"
              @keydown.enter.prevent="go(`/pages/detail/detail?id=${selected.question_id}`)"
              @keydown.space.prevent
              @keyup.space.prevent="go(`/pages/detail/detail?id=${selected.question_id}`)"
            >
              查看对应错题
            </button>
          </div>
        </template>
      </template>
    </div>
  </div>
</template>

<script setup>
import MathText from '@/components/math-text/math-text.vue'
import CognitionCanvas from '@/components/cognition-canvas/cognition-canvas.vue'

import { computed, ref } from 'vue'
import { onLoad, onShow, onHide, onUnload } from '@/platform/lifecycle.js'
import { getData } from '@/api/index.js'
import { CORE_SUBJECTS as subjects } from '@/constants/education.js'
import { go } from '@/utils/navigation.js'
import { scopedQuestionURL } from '@/utils/learning.js'
import { reportCauses, reportGraph, reportMastery, reportPointKey } from '@/utils/report.js'
const error = ref(''),
  graphError = ref(''),
  graphLoading = ref(false),
  graphLoaded = ref(false)
let graphRequest = 0
let overviewRequest = 0
const overview = ref({ summary: {}, mastery: [], misconceptions: [], trend: [] }),
  graph = ref({ nodes: [], links: [] }),
  selected = ref(null),
  subject = ref(''),
  relationsMode = ref(false),
  showTrend = ref(false),
  graphList = ref(false),
  loading = ref(true)
const categoryLabel = {
  knowledge: '知识点',
  misconception: '错因',
  question: '错题',
  strategy: '学习方法',
}
const trend = computed(() => overview.value.trend?.slice(-8) || []),
  mastery = computed(() => reportMastery(overview.value.mastery || [])),
  progressItem = computed(
    () => mastery.value.find((item) => item.mastery_score < 0.8) || mastery.value[0],
  ),
  stableItem = computed(() =>
    mastery.value.find(
      (item) =>
        item.mastery_score >= 0.7 &&
        reportPointKey(item) !== reportPointKey(progressItem.value || {}),
    ),
  ),
  attentionItem = computed(() => reportCauses(overview.value.misconceptions || [])[0]),
  graphSummary = computed(() =>
    graph.value.mapped_question_count
      ? `已有 ${graph.value.mapped_question_count} 道错题关联到 ${graph.value.nodes?.filter((node) => node.category === 'knowledge').length || 0} 个知识点`
      : '暂无知识关系',
  )
async function load() {
  const current = ++overviewRequest
  loading.value = true
  error.value = ''
  try {
    const result = await getData('/analytics/overview?days=30')
    if (current === overviewRequest) overview.value = result
  } catch (err) {
    if (current === overviewRequest) error.value = err.message || '学习报告暂时无法加载，请重试'
  } finally {
    if (current === overviewRequest) loading.value = false
  }
  return current === overviewRequest
}
function toggleTrend() {
  showTrend.value = !showTrend.value
}
async function loadGraph() {
  const current = ++graphRequest
  graphError.value = ''
  graphLoading.value = true
  graphLoaded.value = false
  graph.value = { nodes: [], links: [] }
  selected.value = null
  try {
    const result = await getData(
      `/analytics/cognition-graph?days=90${subject.value ? `&subject=${encodeURIComponent(subject.value)}` : ''}`,
    )
    if (current === graphRequest) {
      graph.value = reportGraph(result)
      graphLoaded.value = true
    }
  } catch (err) {
    if (current === graphRequest) graphError.value = err.message || '知识关系暂时无法加载'
  } finally {
    if (current === graphRequest) graphLoading.value = false
  }
}
function selectSubject(value) {
  subject.value = value === '全部' ? '' : value
  loadGraph()
}
onLoad((q) => {
  subject.value = q.subject ? decodeURIComponent(q.subject) : ''
  relationsMode.value = q.relations === '1'
})
onShow(async () => {
  if (relationsMode.value) {
    loading.value = false
    error.value = ''
    await loadGraph()
  } else await load()
})
function clear() {
  overviewRequest++
  graphRequest++
  overview.value = { summary: {}, mastery: [], misconceptions: [], trend: [] }
  graph.value = { nodes: [], links: [] }
  graphLoading.value = false
  graphLoaded.value = false
  selected.value = null
}
onHide(clear)
onUnload(clear)
</script>

<style scoped lang="scss">
.relation-summary {
  color: var(--color-text-secondary);
  font-size: 13px;
  margin-bottom: 12px;
}
.graph-list-item {
  display: block;
  width: 100%;
  min-height: 48px;
  padding: 12px 0;
  text-align: left;
  background: transparent;
  font-size: 16px;
  border-bottom: 1px solid var(--color-border);
  border-radius: 0;
}
.record-toggle {
  min-height: 48px;
  padding: 12px 0;
  background: transparent;
  color: var(--color-primary);
  text-align: left;
  font-size: 16px;
  margin: 12px 0;
}

.report-empty {
  padding: 28px;
  margin: 24px 0;
  background: var(--color-surface);
  border-radius: 12px;
}
.empty-title {
  display: block;
  font-size: 20px;
  font-weight: 600;
  margin-bottom: 10px;
}
.report-empty .muted {
  display: block;
  max-width: 420px;
}
.report-empty .small-btn {
  margin-top: 20px;
}
.report-block {
  padding: 15.0px 0;
  border-bottom: 0.5px solid var(--color-border);
}
.report-block:first-child {
  padding-top: 2.0px;
}
.report-block.progress-block {
  padding: 14.0px;
  margin-bottom: 11.0px;
  border: 0.5px solid var(--color-border);
  border-radius: 12.0px;
  background: var(--color-primary-soft);
}
.progress-block .primary-btn {
  margin-top: 12.0px;
}
.block-label,
.block-title,
.block-detail,
.stable-score {
  display: block;
}
.block-label {
  font-size: 11.5px;
  color: var(--color-text-secondary);
  font-weight: 600;
}
.attention-block .block-label {
  color: #9a6416;
}
.attention-block .block-title {
  font-size: 15.0px;
  line-height: 1.6;
}
.block-title {
  font-size: 18.0px;
  font-weight: 650;
  margin-top: 3.5px;
}
.block-detail {
  font-size: 13.0px;
  line-height: 1.7;
  color: var(--color-text-secondary);
  margin-top: 5.0px;
}
.change-line {
  display: flex;
  align-items: center;
  gap: 5.0px;
  margin-top: 6.0px;
}
.change-line b {
  font-size: 26.0px;
  font-weight: 700;
}
.change-line b:last-of-type {
  color: var(--color-primary);
}
.change-line > span {
  padding: 2.5px 6.0px;
  border-radius: 499.5px;
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-size: 10.5px;
}
.stable-score {
  font-size: 12.5px;
  color: var(--color-primary);
  margin-top: 4.0px;
}
.trend-panel {
  padding: 12.0px 6.0px;
  background: #fff;
  border: 0.5px solid var(--color-border);
  border-radius: 10px;
}
.trend-bars {
  height: 105.0px;
  display: flex;
  align-items: flex-end;
  justify-content: space-around;
  gap: 4.0px;
}
.trend-bars > div {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-end;
  height: 100%;
}
.trend-bars > div > div {
  width: 60%;
  max-width: 15.0px;
  border-radius: 3.5px 3.5px 0 0;
  background: var(--color-primary);
}
.trend-bars span {
  font-size: 9.0px;
  color: var(--color-text-secondary);
  margin-top: 3.5px;
}
.filter-scroll {
  white-space: nowrap;
  margin: 10.0px 0 4.0px;
}
.node-detail {
  margin-top: 8.0px;
  padding: 12.0px;
  border-radius: 11.0px;
  background: #fff;
  border: 0.5px solid var(--color-border);
}
.node-detail b,
.node-detail > span:last-of-type {
  display: block;
}
.node-detail b {
  font-size: 14.5px;
  margin-top: 5.0px;
}
.node-detail > span:last-of-type {
  color: var(--color-text-secondary);
  margin-top: 2.5px;
}
</style>
