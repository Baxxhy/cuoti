<template>
  <view class="page">
    <app-header title="本题互动演示" subtitle="用图形理解当前这道题" back />
    <state-panel v-if="!spec.type" :state="error ? 'error' : 'loading'" @retry="load" />
    <view v-else class="page-content">
      <view class="question-context">
        <text>当前题目</text>
        <b>{{ question.question_text }}</b>
      </view>
      <view class="card">
        <view class="visual-picker">
          <view>
            <text class="hint">本题演示</text>
            <b>{{ spec.title }}</b>
          </view>
        </view>
        <text class="visual-goal">{{ spec.teaching_goal }}</text>
        <visualization-canvas :spec="spec" :values="values" />
        <view v-for="variable in spec.interactive_variables" :key="variable.name" class="control">
          <view>
            <text>{{ variable.label || variable.name }}</text>
            <b>{{ values[variable.name] }}</b>
          </view>
          <slider
            :value="values[variable.name]"
            :min="variable.min"
            :max="variable.max"
            :step="variable.step || 1"
            activeColor="#002FA7"
            @changing="values[variable.name] = $event.detail.value"
            @change="values[variable.name] = $event.detail.value"
          />
        </view>
        <view class="task">
          <text>试一试</text>
          <b>{{ spec.student_task }}</b>
          <small>观察重点：{{ spec.expected_observation }}</small>
        </view>
      </view>
      <view class="card">
        <text class="field-label">你发现了什么？</text>
        <textarea
          v-model="observation"
          class="field-textarea"
          placeholder="写下图形或数值的变化…"
        />
        <text v-if="!observation.trim()" class="disabled-help">先写下你的观察，再继续教学</text>
        <button class="primary-btn" :disabled="busy || !observation.trim() || !id" @click="save">
          {{ busy ? '正在保存…' : '保存并继续' }}
        </button>
      </view>
    </view>
  </view>
</template>
<script setup>
import VisualizationCanvas from '@/components/visualization-canvas/visualization-canvas.vue'
import { reactive, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { getData, postData } from '@/api/index.js'
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
  border-left: 5rpx solid var(--color-warning);
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
