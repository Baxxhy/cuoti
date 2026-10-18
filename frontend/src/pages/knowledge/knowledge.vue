<template>
  <view class="page knowledge-page">
    <app-header
      title="本题知识"
      :subtitle="item ? `${item.subject} · ${item.grade || ''}` : ''"
      back
    />
    <state-panel
      v-if="loading || error"
      :state="error ? 'error' : 'loading'"
      :message="error"
      @retry="load"
    />
    <view v-else-if="item" class="page-content">
      <view class="intro-card">
        <text class="eyebrow">围绕本题，学清一个知识点</text>
        <math-text class="intro-title" :text="primaryKnowledge[0] || '先核对本题内容'" inline />
        <text class="intro-desc">{{ state.message }}</text>
      </view>

      <view class="section-title">本题涉及</view>
      <view class="knowledge-card">
        <view v-for="(name, index) in visibleKnowledge" :key="name" class="knowledge-row">
          <text class="node-number">{{ String(index + 1).padStart(2, '0') }}</text>
          <math-text class="row-name" :text="name" inline />
        </view>
        <text v-if="!primaryKnowledge.length" class="empty-text">
          尚未确定知识点，先核对原题并完成分析。
        </text>
        <button
          v-if="primaryKnowledge.length > 3"
          class="expand-btn"
          :aria-expanded="showAllKnowledge"
          @click="showAllKnowledge = !showAllKnowledge"
        >
          {{ showAllKnowledge ? '收起知识点' : `查看全部 ${primaryKnowledge.length} 个知识点` }}
        </button>
      </view>

      <template v-if="prerequisiteKnowledge.length">
        <view class="section-title">{{ hasFinding ? '可以先复习' : '相关基础' }}</view>
        <view class="knowledge-card">
          <view v-for="name in visiblePrerequisites" :key="name" class="knowledge-row">
            <uni-icons type="arrow-right" size="18" color="var(--color-primary)" />
            <math-text class="row-name" :text="name" inline />
          </view>
          <button
            v-if="prerequisiteKnowledge.length > 2"
            class="expand-btn"
            :aria-expanded="showAllPrerequisites"
            @click="showAllPrerequisites = !showAllPrerequisites"
          >
            {{ showAllPrerequisites ? '收起相关基础' : '展开更多基础' }}
          </button>
        </view>
      </template>

      <view class="diagnosis-card" :class="{ finding: hasFinding }">
        <view class="diagnosis-head">
          <uni-icons
            :type="state.kind === 'clear' ? 'checkmarkempty' : 'info'"
            size="20"
            color="var(--color-primary)"
          />
          <text>{{ state.title }}</text>
        </view>
        <template v-if="hasFinding">
          <text class="finding-label">
            {{ state.step ? `第 ${state.step} 步 · ` : ''
            }}{{ errorTypeLabel(item.diagnosis.error_type) }}
          </text>
          <math-text
            class="diagnosis-reason"
            :text="item.diagnosis.root_misconception || '结合原作答核对这一步。'"
            inline
          />
          <button
            v-if="item.diagnosis.first_error_text"
            class="expand-btn"
            :aria-expanded="showWork"
            @click="showWork = !showWork"
          >
            {{ showWork ? '收起对应作答' : '查看对应作答' }}
          </button>
          <view v-if="showWork" class="work-quote">
            <text>当时的作答</text>
            <math-text :text="item.diagnosis.first_error_text" inline />
          </view>
        </template>
        <text v-else class="status-copy">
          {{
            state.kind === 'review'
              ? '补充解题步骤后，可以更具体地核对问题。'
              : state.kind === 'clear'
                ? '这不代表所有同类题都已掌握。'
                : '知识关联以本题实际分析为准。'
          }}
        </text>
      </view>
      <button role="button" class="primary-btn" @click="continueLearning">
        {{
          !item.analysis
            ? '分析这道题'
            : state.kind === 'missing' || state.kind === 'review'
              ? '核对本次作答'
              : '回到本题学习'
        }}
      </button>
      <button v-if="hasFinding" class="secondary-btn" @click="openDiagnosis">核对诊断</button>
    </view>
  </view>
</template>

<script setup>
import { computed, ref } from 'vue'
import { onLoad, onShow, onHide, onUnload } from '@dcloudio/uni-app'
import { getData } from '@/api/index.js'
import { go, returnToQuestion } from '@/utils/navigation.js'
import { diagnosisView } from '@/utils/diagnosis.js'
import { errorTypeLabel } from '@/constants/education.js'

const id = ref(''),
  item = ref(null),
  loading = ref(true),
  error = ref('')
const showAllKnowledge = ref(false),
  showAllPrerequisites = ref(false),
  showWork = ref(false)
let active = false,
  revision = 0
const unique = (values) => [
  ...new Set(
    values
      .filter((value) => typeof value === 'string')
      .map((value) => value.trim())
      .filter(Boolean),
  ),
]
const state = computed(() => diagnosisView(item.value))
const hasFinding = computed(() => state.value.kind === 'finding')
const primaryKnowledge = computed(() =>
  unique([
    ...(item.value?.analysis?.knowledge_points || []),
    ...(item.value?.knowledge_points || []),
  ]),
)
const prerequisiteKnowledge = computed(() =>
  unique([
    ...(hasFinding.value ? item.value?.diagnosis?.missing_prerequisites || [] : []),
    ...(item.value?.analysis?.prerequisites || []),
  ]).filter((name) => !primaryKnowledge.value.includes(name)),
)
const visibleKnowledge = computed(() =>
  showAllKnowledge.value ? primaryKnowledge.value : primaryKnowledge.value.slice(0, 3),
)
const visiblePrerequisites = computed(() =>
  showAllPrerequisites.value
    ? prerequisiteKnowledge.value
    : prerequisiteKnowledge.value.slice(0, 2),
)
async function load() {
  if (!active) return
  const current = ++revision
  loading.value = true
  error.value = ''
  item.value = null
  showAllKnowledge.value = showAllPrerequisites.value = showWork.value = false
  try {
    if (!id.value) throw new Error('请从具体题目打开本题知识')
    const value = await getData(`/questions/${encodeURIComponent(id.value)}`)
    if (active && revision === current) item.value = value
  } catch (err) {
    if (active && revision === current) error.value = err.message || '本题知识暂时无法加载，请重试'
  } finally {
    if (active && revision === current) loading.value = false
  }
}
function openDiagnosis() {
  go(`/pages/diagnosis/diagnosis?id=${encodeURIComponent(id.value)}`)
}
function continueLearning() {
  if (!item.value.analysis || ['missing', 'review'].includes(state.value.kind))
    return openDiagnosis()
  returnToQuestion(id.value)
}
onLoad((query) => {
  id.value = query.id || ''
})
onShow(() => {
  active = true
  load()
})
function leave() {
  active = false
  revision++
  item.value = null
}
onHide(leave)
onUnload(leave)
</script>

<style scoped lang="scss">
.knowledge-page {
  min-height: 100vh;
  background: var(--color-bg);
}
.intro-card {
  padding: 24px;
  border-radius: 18px;
  background: var(--color-primary);
  color: #fff;
}
.eyebrow {
  display: block;
  color: rgba(255, 255, 255, 0.85);
  font-size: 13px;
  line-height: 1.5;
}
.intro-title {
  margin-top: 12px;
  font-size: 25px;
  font-weight: 700;
  line-height: 1.4;
}
.intro-desc {
  display: block;
  margin-top: 12px;
  color: rgba(255, 255, 255, 0.9);
  font-size: 14px;
  line-height: 1.65;
}
.section-title {
  margin: 28px 0 12px;
  color: var(--color-text);
  font-size: 17px;
  font-weight: 700;
}
.knowledge-card,
.diagnosis-card {
  border: 1px solid var(--color-border);
  border-radius: 16px;
  background: var(--color-surface, #fff);
  overflow: hidden;
}
.knowledge-row {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 18px;
}
.knowledge-row + .knowledge-row {
  border-top: 1px solid var(--color-border);
}
.node-number {
  flex: none;
  color: var(--color-primary);
  font-size: 13px;
  font-weight: 700;
}
.row-name {
  min-width: 0;
  color: var(--color-text);
  font-size: 16px;
  line-height: 1.5;
}
.empty-text,
.status-copy {
  display: block;
  color: var(--color-text-secondary);
  font-size: 14px;
  line-height: 1.65;
}
.empty-text {
  padding: 20px;
}
.expand-btn {
  width: 100%;
  min-height: 44px;
  margin: 0;
  padding: 12px 18px;
  border: 0;
  border-radius: 0;
  background: transparent;
  color: var(--color-primary);
  text-align: left;
  font-size: 14px;
  line-height: 1.5;
}
.expand-btn::after {
  border: 0;
}
.diagnosis-card {
  margin-top: 24px;
  padding: 20px;
}
.diagnosis-head {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--color-text);
  font-size: 16px;
  font-weight: 600;
}
.finding-label {
  display: block;
  margin-top: 14px;
  color: var(--color-text-secondary);
  font-size: 13px;
}
.diagnosis-reason,
.status-copy {
  margin-top: 12px;
}
.diagnosis-reason {
  font-size: 15px;
  line-height: 1.7;
}
.diagnosis-card .expand-btn {
  padding-left: 0;
  padding-bottom: 0;
}
.work-quote {
  margin-top: 12px;
  padding: 14px;
  border-left: 2px solid var(--color-primary);
  background: var(--color-bg);
}
.work-quote > text {
  display: block;
  margin-bottom: 8px;
  color: var(--color-text-secondary);
  font-size: 12px;
}
.primary-btn {
  width: 100%;
  margin-top: 24px;
}
.secondary-btn {
  width: 100%;
  margin-top: 12px;
}
</style>
