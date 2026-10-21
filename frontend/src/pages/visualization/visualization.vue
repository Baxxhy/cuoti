<template>
  <view class="page">
    <app-header title="互动图解" back />
    <state-panel
      v-if="!spec.type"
      :state="!id || error ? 'error' : 'loading'"
      :message="!id ? '请先选择一道错题' : undefined"
      :retry-text="!id ? '选择错题' : '重新加载'"
      @retry="id ? load() : go('/pages/problem/list')"
    />
    <view v-else class="page-content">
      <view class="question-context">
        <text>当前题目</text>
        <b><math-text :text="question.question_text" inline /></b>
      </view>
      <view class="card">
        <view class="visual-picker">
          <view>
            <text class="hint">本题演示</text>
            <b><math-text :text="spec.title" inline /></b>
          </view>
        </view>
        <math-text class="visual-goal" :text="spec.teaching_goal" inline />
        <visualization-canvas :spec="spec" :values="values" />
        <view v-for="variable in spec.interactive_variables" :key="variable.name" class="control">
          <view>
            <math-text :text="variable.label || variable.name" inline />
            <b>{{ values[variable.name] }}</b>
          </view>
          <slider
            :value="values[variable.name]"
            :min="variable.min"
            :max="variable.max"
            :step="variable.step || 1"
            activeColor="var(--color-primary)"
            @changing="values[variable.name] = $event.detail.value"
            @change="values[variable.name] = $event.detail.value"
          />
        </view>
        <view class="task">
          <text>试一试</text>
          <b><math-text :text="spec.student_task" inline /></b>
          <button
            role="button"
            v-if="spec.expected_observation"
            class="observation-toggle"
            :aria-expanded="showObservation"
            @click="showObservation = !showObservation"
          >
            {{ showObservation ? '收起观察提示' : '查看观察提示' }}
          </button>
          <math-text v-if="showObservation" :text="spec.expected_observation" inline />
        </view>
      </view>
      <view class="card">
        <text class="field-label">你发现了什么？</text>
        <textarea
          v-model="observation"
          class="field-textarea"
          aria-label="图解观察"
          placeholder="写下图形或数值的变化"
        />
        <text v-if="!observation.trim()" class="disabled-help">先写下你的观察，再继续教学</text>
        <button
          role="button"
          class="primary-btn"
          :disabled="busy || !observation.trim() || !id"
          @click="save"
        >
          {{ busy ? '正在保存…' : '保存观察并返回' }}
        </button>
      </view>
    </view>
  </view>
</template>
<script setup>
import { go } from '@/utils/navigation.js'
import MathText from '@/components/math-text/math-text.vue'
import VisualizationCanvas from '@/components/visualization-canvas/visualization-canvas.vue'
import { reactive, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { getData, postData } from '@/api/index.js'
const showObservation = ref(false)
const id = ref(''),
  spec = ref({}),
  question = ref({}),
  values = reactive({}),
  observation = ref(''),
  error = ref(false),
  busy = ref(false)
function reset() {
  Object.keys(values).forEach((k) => delete values[k])
  ;(spec.value.interactive_variables || []).forEach((v) => (values[v.name] = v.value))
}
async function load() {
  if (!id.value) return
  error.value = false
  try {
    const data = await getData(`/tutor/sessions/${id.value}/visualization`)
    spec.value = data.spec
    question.value = data.question
    reset()
  } catch {
    error.value = true
  }
}
async function save() {
  if (busy.value || !observation.value.trim() || !id.value) return
  busy.value = true
  try {
    await postData(`/tutor/sessions/${id.value}/visualization`, {
      values: { ...values },
      observation: observation.value,
    })
    uni.redirectTo({ url: `/pages/tutor/tutor?id=${id.value}` })
  } catch {
  } finally {
    busy.value = false
  }
}
onLoad((q) => {
  id.value = q.id || ''
  load()
})
</script>
<style scoped lang="scss">
.observation-toggle {
  margin: 8px 0 0;
  padding: 10px 0;
  min-height: 44px;
  font-size: 14px;
  color: var(--color-primary);
  background: transparent;
  text-align: left;
}
.question-context {
  padding: 24rpx;
  margin-bottom: 18rpx;
  border-radius: 22rpx;
  background: var(--color-primary-soft);
  border: 1rpx solid var(--color-primary-border);
}
.question-context text,
.question-context b {
  display: block;
}
.question-context text {
  font-size: 22rpx;
  color: var(--color-primary);
}
.question-context b {
  margin-top: 8rpx;
  font-size: 27rpx;
  line-height: 1.6;
  color: var(--color-text-primary);
  font-weight: 600;
}
.visual-picker {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20rpx;
  background: var(--color-primary-soft);
  border-radius: 18rpx;
  margin-bottom: 18rpx;
}
.visual-picker text,
.visual-picker b {
  display: block;
}
.visual-picker b {
  font-size: 29rpx;
  color: var(--color-primary);
  margin-top: 4rpx;
  font-weight: 600;
}
.visual-goal {
  display: block;
  color: var(--color-text-secondary);
  font-size: 24rpx;
  margin: 18rpx 0;
}
.control {
  margin-top: 24rpx;
}
.control > view {
  display: flex;
  justify-content: space-between;
  font-size: 24rpx;
}
.control b {
  color: var(--color-primary);
}
.control slider {
  margin: 5rpx 0;
}
.task {
  margin-top: 26rpx;
  padding: 22rpx;
  border-radius: 18rpx;
  background: var(--color-warning-soft);
}
.task text,
.task b,
.task small {
  display: block;
}
.task text {
  color: #9a6416;
  font-size: 22rpx;
}
.task b {
  margin-top: 7rpx;
  font-weight: 600;
}
.task small {
  color: #6f4a14;
  font-size: 21rpx;
  margin-top: 7rpx;
}
</style>
