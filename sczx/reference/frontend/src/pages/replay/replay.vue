<template>
  <view class="page replay-page">
    <app-header
      title="错因回放"
      back
      :back-fallback="id ? `/pages/detail/detail?id=${id}` : '/pages/problem/list'"
    />
    <view class="page-content">
      <state-panel
        v-if="loading || error"
        :state="error ? 'error' : 'loading'"
        :message="error"
        :retry-text="!id ? '选择错题' : '重新加载'"
        @retry="id ? load() : go('/pages/problem/list')"
      />
      <template v-else-if="item">
        <view class="editorial-heading">
          <text class="eyebrow">{{ item.subject }} · 当时的解题过程</text>
        </view>
        <button
          role="button"
          tabindex="0"
          class="disclosure-link"
          :aria-expanded="showQuestion"
          @keydown.enter.prevent="showQuestion = !showQuestion"
          @keydown.space.prevent
          @keyup.space.prevent="showQuestion = !showQuestion"
          @click="showQuestion = !showQuestion"
        >
          {{ showQuestion ? '收起题目' : '查看原题' }}
          <uni-icons aria-hidden="true" :type="showQuestion ? 'top' : 'bottom'" size="18" />
        </button>
        <view v-if="showQuestion" class="replay-question">
          <math-text :text="item.question_text" />
          <math-text
            v-for="(option, i) in item.options || []"
            :key="i"
            :text="optionText(option, i)"
          />
          <button
            aria-label="查看完整题目与原图"
            role="button"
            tabindex="0"
            class="disclosure-link"
            @click="go(`/pages/detail/detail?id=${id}`)"
            @keydown.enter.prevent="go(`/pages/detail/detail?id=${id}`)"
            @keydown.space.prevent
            @keyup.space.prevent="go(`/pages/detail/detail?id=${id}`)"
          >
            查看完整题目与原图
            <uni-icons aria-hidden="true" type="right" size="18" />
          </button>
        </view>
        <template v-if="steps.length">
          <scroll-view class="step-navigation" scroll-x>
            <view class="step-buttons">
              <button
                role="button"
                tabindex="0"
                v-for="(step, i) in steps"
                :key="step.id || i"
                :aria-pressed="index === i"
                :aria-label="`查看第${i + 1}步${step.first ? '，诊断指向此处' : ''}`"
                :class="{ active: index === i, flagged: step.first }"
                @keydown.enter.prevent="index = i"
                @keydown.space.prevent
                @keyup.space.prevent="index = i"
                @click="index = i"
              >
                {{ i + 1 }}
                <text v-if="step.first">待核对</text>
              </button>
            </view>
          </scroll-view>
          <view v-if="current" class="replay-stage">
            <view class="replay-stage-top">
              <text>第 {{ index + 1 }} / {{ steps.length }} 步</text>
              <text :class="current.first ? 'status-warning' : ''">
                {{ current.first ? '可能最早出错的一步' : '核对这一步' }}
              </text>
            </view>
            <view class="comparison-grid">
              <view class="comparison-side student-side">
                <text class="eyebrow">你的原始步骤</text>
                <math-text :text="current.text" />
              </view>
              <view class="comparison-side reference-side">
                <text class="eyebrow">对应的参考思路</text>
                <template v-if="current.aligned">
                  <math-text
                    v-for="reference in current.references"
                    :key="reference.id"
                    :text="reference.text"
                  />
                </template>
                <text v-else class="editorial-description">
                  暂时找不到对应的参考步骤。你可以补充解题过程，或查看完整解析。
                </text>
              </view>
            </view>
            <view class="replay-explanation">
              <text class="eyebrow">{{ current.first ? '为什么需要检查' : '这一步的说明' }}</text>
              <math-text
                :text="
                  current.reason ||
                  (current.first ? item.diagnosis?.root_misconception : '') ||
                  '这一步还没有分析结果，请对照参考解法检查。'
                "
              />
            </view>
            <view v-if="current.evidence.length" class="evidence-caption">
              根据本次错因分析整理。{{
                item.diagnosis?.user_confirmed ? '你已核对过诊断。' : '仍需结合原作答核对。'
              }}
            </view>
            <view class="replay-controls">
              <button
                role="button"
                tabindex="0"
                class="secondary-btn"
                :disabled="index === 0"
                @keydown.enter.prevent="index--"
                @keydown.space.prevent
                @keyup.space.prevent="index--"
                @click="index--"
              >
                上一步
              </button>
              <button
                role="button"
                tabindex="0"
                class="secondary-btn"
                :disabled="index === steps.length - 1"
                @keydown.enter.prevent="index++"
                @keydown.space.prevent
                @keyup.space.prevent="index++"
                @click="index++"
              >
                下一步
              </button>
            </view>
          </view>
        </template>
        <view v-else class="composed-empty">
          <text class="editorial-title">还缺少你的解题过程</text>
          <text class="editorial-description">
            只有最后答案，不能判断首次出错的位置。补充真实步骤后再核对。
          </text>
        </view>
        <view class="replay-next">
          <button
            role="button"
            tabindex="0"
            class="primary-btn"
            @keydown.enter.prevent="go(`/pages/repair/repair?id=${id}`)"
            @keydown.space.prevent
            @keyup.space.prevent="go(`/pages/repair/repair?id=${id}`)"
            @click="go(`/pages/repair/repair?id=${id}`)"
          >
            查看学习安排
          </button>
          <button
            aria-label="核对诊断或纠正错因"
            role="button"
            tabindex="0"
            class="disclosure-link"
            @keydown.enter.prevent="go(`/pages/diagnosis/diagnosis?id=${id}`)"
            @keydown.space.prevent
            @keyup.space.prevent="go(`/pages/diagnosis/diagnosis?id=${id}`)"
            @click="go(`/pages/diagnosis/diagnosis?id=${id}`)"
          >
            核对诊断或纠正错因
            <uni-icons aria-hidden="true" type="right" size="18" />
          </button>
          <button
            aria-label="补充或修改当时的作答"
            role="button"
            tabindex="0"
            class="disclosure-link"
            @keydown.enter.prevent="go(`/pages/ocr/ocr?id=${id}&edit=1`)"
            @keydown.space.prevent
            @keyup.space.prevent="go(`/pages/ocr/ocr?id=${id}&edit=1`)"
            @click="go(`/pages/ocr/ocr?id=${id}&edit=1`)"
          >
            补充或修改当时的作答
            <uni-icons aria-hidden="true" type="right" size="18" />
          </button>
        </view>
      </template>
    </view>
  </view>
</template>
<script setup>
import { computed, ref } from 'vue'
import { onLoad, onShow, onHide, onUnload } from '@dcloudio/uni-app'
import { getData } from '@/api/index.js'
import { go } from '@/utils/navigation.js'
import { replaySteps } from '@/utils/repair.js'
const id = ref(''),
  item = ref(null),
  loading = ref(true),
  error = ref(''),
  index = ref(0),
  showQuestion = ref(false)
let revision = 0
let lastSource = ''
const steps = computed(() => replaySteps(item.value)),
  current = computed(() => steps.value[index.value])
function optionText(option, i) {
  return typeof option === 'string'
    ? option
    : `${option?.label || option?.key || String.fromCharCode(65 + i)}. ${option?.text || option?.content || option?.value || ''}`
}
async function load() {
  const version = ++revision
  loading.value = true
  error.value = ''
  try {
    if (!id.value) throw new Error('请从一道错题进入回放。')
    const result = await getData(`/questions/${encodeURIComponent(id.value)}`)
    if (version !== revision) return
    if (result.status === 'archived') throw new Error('这道题已归档，请返回错题列表。')
    item.value = result
    const first = replaySteps(result).findIndex((step) => step.first)
    const source = `${result.id}:${result.diagnosis?.id || ''}:${result.diagnosis?.updated_at || ''}:${result.student_steps?.[0]?.id || ''}`
    index.value =
      source === lastSource
        ? Math.min(index.value, Math.max(0, replaySteps(result).length - 1))
        : first < 0
          ? 0
          : first
    lastSource = source
  } catch (err) {
    if (version === revision) error.value = err.message || '回放暂时无法读取'
  } finally {
    if (version === revision) loading.value = false
  }
}
function clear() {
  revision++
  item.value = null
}
onLoad((query) => {
  id.value = query.id || ''
})
onShow(load)
onHide(clear)
onUnload(clear)
</script>
<style scoped lang="scss">
.replay-question {
  display: block;
  padding: 16px 0;
  border-bottom: 1px solid var(--color-border);
}
.step-navigation {
  margin: 24px 0;
  white-space: nowrap;
}
.step-buttons {
  display: flex;
  gap: 8px;
}
.step-buttons button {
  margin: 0;
  padding: 10px 14px;
  min-width: 48px;
  min-height: 48px;
  flex-shrink: 0;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  font-variant-numeric: tabular-nums;
  font-size: 16px;
}
.step-buttons button.active {
  border-color: var(--color-primary);
  color: var(--color-primary);
  background: var(--color-primary-soft);
}
.step-buttons button text {
  margin-left: 6px;
  font-size: 12px;
}
.replay-stage {
  padding-top: 8px;
}
.replay-stage-top {
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  padding: 16px 0;
  font-size: 13px;
  color: var(--color-text-secondary);
}
.status-warning {
  color: var(--color-warning);
}
.comparison-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  border-top: 1px solid var(--color-border);
  border-bottom: 1px solid var(--color-border);
}
.comparison-side {
  min-width: 0;
  padding: 24px 20px;
  background: var(--color-surface);
}
.comparison-side .eyebrow {
  margin-bottom: 20px;
}
.reference-side {
  border-left: 1px solid var(--color-border);
  background: var(--color-primary-soft);
}
.replay-explanation {
  padding: 24px 0;
}
.replay-explanation .eyebrow {
  margin-bottom: 12px;
}
.evidence-caption {
  font-size: 13px;
  line-height: 1.7;
  color: var(--color-text-secondary);
}
.replay-controls {
  display: flex;
  gap: 12px;
  margin: 24px 0;
}
.replay-controls button {
  flex: 1;
  margin: 0;
}
.replay-next {
  border-top: 1px solid var(--color-border);
  padding-top: 24px;
}
@media (max-width: 600px) {
  .comparison-grid {
    grid-template-columns: 1fr;
  }
  .reference-side {
    border-left: 0;
    border-top: 1px solid var(--color-border);
  }
  .comparison-side {
    padding: 20px 16px;
  }
}
</style>
