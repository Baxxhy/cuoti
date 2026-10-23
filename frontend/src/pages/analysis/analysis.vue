<template>
  <view class="page report-page">
    <app-header :title="relationsMode ? '知识关系' : '学习报告'" back />
    <view class="page-content">
      <state-panel
        v-if="loading || error"
        :state="error ? 'error' : 'loading'"
        :message="error"
        @retry="load"
      />
      <template v-else>
        <template v-if="!relationsMode">
          <view
            v-if="!progressItem && !attentionItem && !stableItem && !trend.length"
            class="report-empty"
          >
            <text class="empty-title">还没有学习报告</text>
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
          </view>
          <view v-if="progressItem" class="report-block progress-block">
            <text class="block-label">{{ progressItem.subject }} · 近期学习</text>
            <template v-if="progressItem">
              <math-text class="block-title" :text="progressItem.knowledge_point" inline />
              <view class="change-line">
                <b>{{ Math.round(progressItem.mastery_score * 100) }}%</b>
                <text>学习记录估计</text>
              </view>
              <text class="block-detail"></text>
              <button
                class="primary-btn"
                role="button"
                @click="go(scopedQuestionURL({ subject: progressItem.subject || '' }))"
              >
                查看{{ progressItem.subject }}错题
              </button>
            </template>
            <text v-else class="muted">完成学习后，这里会显示实际掌握记录。</text>
          </view>

          <view v-if="attentionItem" class="report-block attention-block">
            <text class="block-label">{{ attentionItem.subject }} · 最需要注意</text>
            <template v-if="attentionItem">
              <math-text class="block-title" :text="attentionItem.label" />
              <text class="block-detail"></text>
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
            <text v-else class="muted">目前没有集中出现的错因。</text>
          </view>

          <view v-if="stableItem" class="report-block stable-block">
            <text class="block-label">{{ stableItem.subject }} · 正在稳定</text>
            <template v-if="stableItem">
              <math-text class="block-title" :text="stableItem.knowledge_point" inline />
              <text class="stable-score">
                学习记录估计 {{ Math.round(stableItem.mastery_score * 100) }}%
              </text>
              <text class="block-detail"></text>
            </template>
            <text v-else class="muted">掌握度达到较稳定状态后会显示在这里。</text>
          </view>

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
          <view v-if="trend.length && showTrend" class="trend-panel">
            <text class="muted">不同日期涉及的知识点可能不同。</text>
            <view class="trend-bars">
              <view v-for="point in trend" :key="point.date">
                <view :style="{ height: Math.max(8, point.score * 1.4) + 'rpx' }" />
                <text>{{ point.date?.slice(5) }}</text>
              </view>
            </view>
            <text v-if="!trend.length" class="muted">完成练习后显示趋势</text>
          </view>
        </template>
        <template v-if="relationsMode">
          <view class="relation-summary">
            <text v-if="graphLoaded">{{ graphSummary }}</text>
          </view>
          <scroll-view scroll-x class="filter-scroll">
            <view class="chip-row">
              <text
                v-for="value in ['全部', ...subjects]"
                :key="value"
                class="chip"
                :class="{ active: subject === (value === '全部' ? '' : value) }"
                @click="selectSubject(value)"
              >
                {{ value }}
              </text>
            </view>
          </scroll-view>
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
            <view v-if="graphList" class="graph-list">
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
              <text v-if="!graph.nodes?.length" class="muted">还没有可查看的知识关系</text>
            </view>
            <cognition-canvas v-else :graph="graph" @select="selected = $event" />
          </template>
          <view v-if="selected" class="node-detail">
            <text class="tag">{{ categoryLabel[selected.category] || '学习关系' }}</text>
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
          </view>
        </template>
      </template>
    </view>
  </view>
</template>

<script setup>
import MathText from '@/components/math-text/math-text.vue'
import CognitionCanvas from '@/components/cognition-canvas/cognition-canvas.vue'

import { computed, ref } from 'vue'
import { onLoad, onShow, onHide, onUnload } from '@dcloudio/uni-app'
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
  padding: 30rpx 0;
  border-bottom: 1rpx solid var(--color-border);
}
.report-block:first-child {
  padding-top: 4rpx;
}
.report-block.progress-block {
  padding: 28rpx;
  margin-bottom: 22rpx;
  border: 1rpx solid var(--color-border);
  border-radius: 24rpx;
  background: var(--color-primary-soft);
}
.progress-block .primary-btn {
  margin-top: 24rpx;
}
.block-label,
.block-title,
.block-detail,
.stable-score {
  display: block;
}
.block-label {
  font-size: 23rpx;
  color: var(--color-text-secondary);
  font-weight: 600;
}
.attention-block .block-label {
  color: #9a6416;
}
.attention-block .block-title {
  font-size: 30rpx;
  line-height: 1.6;
}
.block-title {
  font-size: 36rpx;
  font-weight: 650;
  margin-top: 7rpx;
}
.block-detail {
  font-size: 26rpx;
  line-height: 1.7;
  color: var(--color-text-secondary);
  margin-top: 10rpx;
}
.change-line {
  display: flex;
  align-items: center;
  gap: 10rpx;
  margin-top: 12rpx;
}
.change-line b {
  font-size: 52rpx;
  font-weight: 700;
}
.change-line b:last-of-type {
  color: var(--color-primary);
}
.change-line > text {
  padding: 5rpx 12rpx;
  border-radius: 999rpx;
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-size: 21rpx;
}
.stable-score {
  font-size: 25rpx;
  color: var(--color-primary);
  margin-top: 8rpx;
}
.trend-panel {
  padding: 24rpx 12rpx;
  background: #fff;
  border: 1rpx solid var(--color-border);
  border-radius: 10px;
}
.trend-bars {
  height: 210rpx;
  display: flex;
  align-items: flex-end;
  justify-content: space-around;
  gap: 8rpx;
}
.trend-bars > view {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-end;
  height: 100%;
}
.trend-bars > view > view {
  width: 60%;
  max-width: 30rpx;
  border-radius: 7rpx 7rpx 0 0;
  background: var(--color-primary);
}
.trend-bars text {
  font-size: 18rpx;
  color: var(--color-text-secondary);
  margin-top: 7rpx;
}
.filter-scroll {
  white-space: nowrap;
  margin: 20rpx 0 8rpx;
}
.node-detail {
  margin-top: 16rpx;
  padding: 24rpx;
  border-radius: 22rpx;
  background: #fff;
  border: 1rpx solid var(--color-border);
}
.node-detail b,
.node-detail > text:last-of-type {
  display: block;
}
.node-detail b {
  font-size: 29rpx;
  margin-top: 10rpx;
}
.node-detail > text:last-of-type {
  color: var(--color-text-secondary);
  margin-top: 5rpx;
}
</style>
