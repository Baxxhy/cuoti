<template>
  <view class="page error-map-page">
    <app-header title="个人易错地图" subtitle="每个线索，都能回到原题核对" back />
    <view class="page-content">
      <view class="editorial-heading map-heading">
        <text class="eyebrow">最近90天 · 本人的有效题目</text>
        <text class="editorial-title">把重复的问题，连起来看。</text>
        <text class="editorial-description">
          按已有诊断归组，不预测考试失分，也不把一次错误当作固定弱项。
        </text>
      </view>
      <scroll-view scroll-x class="map-filters">
        <view class="map-filter-row">
          <button
            role="button"
            tabindex="0"
            v-for="value in ['全部', ...subjects]"
            :key="value"
            :aria-pressed="subject === (value === '全部' ? '' : value)"
            :class="{ active: subject === (value === '全部' ? '' : value) }"
            @keydown.enter.prevent="selectSubject(value)"
            @keydown.space.prevent
            @keyup.space.prevent="selectSubject(value)"
            @click="selectSubject(value)"
          >
            {{ value }}
          </button>
        </view>
      </scroll-view>
      <state-panel
        v-if="loading || error"
        :state="error ? 'error' : 'loading'"
        :message="error"
        @retry="load"
      />
      <template v-else>
        <view v-if="!groups.length" class="composed-empty">
          <text class="editorial-title">先留下可以核对的线索</text>
          <text class="editorial-description">
            当前范围还没有明确错因。录入真实作答并完成诊断后，再来看它们的联系。
          </text>
          <button
            role="button"
            tabindex="0"
            class="primary-btn"
            @keydown.enter.prevent="go('/pages/problem/list')"
            @keydown.space.prevent
            @keyup.space.prevent="go('/pages/problem/list')"
            @click="go('/pages/problem/list')"
          >
            查看我的题目
          </button>
          <button
            aria-label="录入一道题"
            role="button"
            tabindex="0"
            class="disclosure-link"
            @keydown.enter.prevent="go('/pages/capture/capture')"
            @keydown.space.prevent
            @keyup.space.prevent="go('/pages/capture/capture')"
            @click="go('/pages/capture/capture')"
          >
            录入一道题
            <uni-icons aria-hidden="true" type="right" size="18" />
          </button>
        </view>
        <template v-else>
          <view class="map-summary">
            <text>{{ groups.length }} 类诊断线索</text>
            <text>{{ sourceCount }} 道关联题目</text>
          </view>
          <view class="evidence-map-layout">
            <view class="map-directory" :class="{ single: groups.length === 1 }">
              <button
                role="button"
                tabindex="0"
                v-for="(group, i) in groups"
                :key="group.key"
                class="map-node"
                :class="{ selected: selected?.key === group.key }"
                :aria-pressed="selected?.key === group.key"
                @keydown.enter.prevent="selectedKey = group.key"
                @keydown.space.prevent
                @keyup.space.prevent="selectedKey = group.key"
                @click="selectedKey = group.key"
              >
                <text class="node-number">{{ String(i + 1).padStart(2, '0') }}</text>
                <view class="node-copy">
                  <text>{{ group.label }}</text>
                  <small>
                    {{ group.subject }} ·
                    {{
                      group.sources.length > 1
                        ? `${group.sources.length}道题中重复出现`
                        : '1道题中的线索'
                    }}
                  </small>
                </view>
                <uni-icons aria-hidden="true" type="right" size="18" />
              </button>
            </view>
            <view v-if="selected" class="map-evidence">
              <view class="evidence-heading">
                <text class="eyebrow">{{ selected.subject }} · 诊断来源</text>
                <text class="evidence-title">{{ selected.label }}</text>
                <text class="editorial-description">
                  {{
                    selected.due
                      ? `${selected.due}道关联题已有到期复习安排。`
                      : '先核对原题，再决定从哪里修复。'
                  }}
                </text>
              </view>
              <view v-if="selected.points.length" class="point-labels">
                <text v-for="point in selected.points" :key="point">{{ point }}</text>
              </view>
              <view v-for="source in selected.sources" :key="source.id" class="map-source">
                <text class="eyebrow">
                  {{ studyDate(source.diagnosis.created_at) }} ·
                  {{ source.diagnosis.user_confirmed ? '已由你核对' : '诊断待核对' }}
                </text>
                <math-text class="source-question" :text="source.question_text" />
                <view class="source-reason">
                  <text>诊断依据</text>
                  <math-text :text="source.diagnosis.root_misconception" />
                </view>
                <view class="source-actions">
                  <button
                    role="button"
                    tabindex="0"
                    @click="go(`/pages/detail/detail?id=${source.id}`)"
                    @keydown.enter.prevent="go(`/pages/detail/detail?id=${source.id}`)"
                    @keydown.space.prevent
                    @keyup.space.prevent="go(`/pages/detail/detail?id=${source.id}`)"
                  >
                    原题与原图
                  </button>
                  <button
                    role="button"
                    tabindex="0"
                    @keydown.enter.prevent="go(`/pages/replay/replay?id=${source.id}`)"
                    @keydown.space.prevent
                    @keyup.space.prevent="go(`/pages/replay/replay?id=${source.id}`)"
                    @click="go(`/pages/replay/replay?id=${source.id}`)"
                  >
                    回放作答
                  </button>
                  <button
                    role="button"
                    tabindex="0"
                    @keydown.enter.prevent="go(`/pages/repair/repair?id=${source.id}`)"
                    @keydown.space.prevent
                    @keyup.space.prevent="go(`/pages/repair/repair?id=${source.id}`)"
                    @click="go(`/pages/repair/repair?id=${source.id}`)"
                  >
                    查看修复路线
                  </button>
                  <button
                    role="button"
                    tabindex="0"
                    v-if="source.due_review_id"
                    @keydown.enter.prevent="go(`/pages/review/review?plan=${source.due_review_id}`)"
                    @keydown.space.prevent
                    @keyup.space.prevent="go(`/pages/review/review?plan=${source.due_review_id}`)"
                    @click="go(`/pages/review/review?plan=${source.due_review_id}`)"
                  >
                    到期复习
                  </button>
                </view>
              </view>
            </view>
          </view>
        </template>
        <text class="evidence-caption map-boundary">
          {{
            truncated
              ? '当前最多读取最近200道已诊断题目，当前地图并非全部历史。'
              : '来源：当前题目版本的最新诊断。'
          }}
          未定位的错因不归入具体分类；已修复的历史诊断仍可回看，是否保持要通过复习验证。
        </text>
      </template>
    </view>
  </view>
</template>
<script setup>
import { computed, ref } from 'vue'
import { onShow, onHide, onUnload } from '@dcloudio/uni-app'
import { getData } from '@/api/index.js'
import { go } from '@/utils/navigation.js'
import { CORE_SUBJECTS as subjects } from '@/constants/education.js'
import { errorGroups } from '@/utils/repair.js'
import { studyDate } from '@/utils/learning.js'
const sources = ref([]),
  subject = ref(''),
  selectedKey = ref(''),
  loading = ref(true),
  error = ref(''),
  truncated = ref(false)
let revision = 0
const groups = computed(() => errorGroups(sources.value)),
  selected = computed(
    () => groups.value.find((group) => group.key === selectedKey.value) || groups.value[0],
  ),
  sourceCount = computed(() => groups.value.reduce((n, group) => n + group.sources.length, 0))
async function load() {
  const version = ++revision
  loading.value = true
  error.value = ''
  sources.value = []
  try {
    const result = await getData(
      `/analytics/error-sources?days=90${subject.value ? `&subject=${encodeURIComponent(subject.value)}` : ''}`,
    )
    if (version === revision) {
      sources.value = result.sources || []
      truncated.value = result.truncated
    }
  } catch (err) {
    if (version === revision) error.value = err.message || '易错地图暂时无法读取'
  } finally {
    if (version === revision) loading.value = false
  }
}
function selectSubject(value) {
  subject.value = value === '全部' ? '' : value
  selectedKey.value = ''
  load()
}
function clear() {
  revision++
  sources.value = []
}
onShow(load)
onHide(clear)
onUnload(clear)
</script>
<style scoped lang="scss">
.map-filters {
  margin: 24px 0 8px;
  white-space: nowrap;
}
.map-filter-row {
  display: flex;
  gap: 8px;
}
.map-filter-row button {
  flex-shrink: 0;
  margin: 0;
  min-height: 44px;
  padding: 10px 16px;
  font-size: 14px;
  background: transparent;
  border-radius: 4px;
}
.map-filter-row button.active {
  background: var(--color-primary-soft);
  color: var(--color-primary);
}
.map-summary {
  display: flex;
  gap: 24px;
  font-size: 13px;
  color: var(--color-text-secondary);
  padding: 16px 0;
  border-bottom: 1px solid var(--color-border);
}
.evidence-map-layout {
  display: grid;
  grid-template-columns: minmax(200px, 0.8fr) minmax(0, 1.7fr);
  gap: 32px;
  margin-top: 8px;
}
.map-node {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  margin: 0;
  padding: 20px 12px;
  min-height: 84px;
  border-radius: 0;
  border-bottom: 1px solid var(--color-border);
  background: transparent;
  text-align: left;
}
.map-node.selected {
  color: var(--color-primary);
  background: var(--color-primary-soft);
  box-shadow: inset 3px 0 var(--color-primary);
}
.node-number {
  font-size: 13px;
  color: var(--color-text-secondary);
  font-variant-numeric: tabular-nums;
}
.node-copy {
  flex: 1;
  min-width: 0;
}
.node-copy text,
.node-copy small {
  display: block;
}
.node-copy text {
  font-size: 16px;
  font-weight: 600;
}
.node-copy small {
  margin-top: 6px;
  color: var(--color-text-secondary);
  font-size: 13px;
}
.evidence-heading {
  padding: 24px 0 12px;
}
.evidence-title {
  display: block;
  margin: 8px 0;
  font-size: 24px;
  font-weight: 650;
}
.point-labels {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 8px 0;
}
.point-labels text {
  padding: 4px 8px;
  border: 1px solid var(--color-border);
  font-size: 13px;
  border-radius: 4px;
}
.map-source {
  border-top: 1px solid var(--color-border);
  padding: 24px 0;
}
.source-question {
  display: block;
  margin: 14px 0;
}
.source-reason {
  padding-left: 14px;
  border-left: 2px solid var(--color-primary-border);
  font-size: 14px;
}
.source-reason > text {
  display: block;
  color: var(--color-text-secondary);
  font-size: 12px;
  margin-bottom: 6px;
}
.source-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 20px;
  margin-top: 16px;
}
.source-actions button {
  margin: 0;
  padding: 8px 0;
  min-height: 44px;
  background: transparent;
  color: var(--color-primary);
  font-size: 14px;
  text-align: left;
}
.map-boundary {
  display: block;
  margin: 24px 0;
}
@media (min-width: 651px) {
  .map-directory {
    position: sticky;
    top: 88px;
    max-height: calc(100vh - 112px);
    overflow-y: auto;
    align-self: start;
  }
}
@media (max-width: 650px) {
  .evidence-map-layout {
    grid-template-columns: 1fr;
    gap: 8px;
  }
  .map-directory {
    display: flex;
    gap: 8px;
    overflow-x: auto;
  }
  .map-node {
    flex: 0 0 240px;
    padding: 14px 8px;
  }
  .map-directory.single .map-node {
    flex-basis: 100%;
  }
  .node-number {
    display: none;
  }
}
</style>
