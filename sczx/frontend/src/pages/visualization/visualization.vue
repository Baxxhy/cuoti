<template>
  <div class="page">
    <app-header title="互动图解" back />
    <state-panel
      v-if="!spec.type"
      :state="!id || error ? 'error' : 'loading'"
      :message="!id ? '请先选择一道错题' : undefined"
      :retry-text="!id ? '选择错题' : '重新加载'"
      @retry="id ? load() : go('/pages/problem/list')"
    />
    <div v-else class="page-content">
      <div class="question-context">
        <span>当前题目</span>
        <b><math-text :text="question.question_text" inline /></b>
      </div>
      <div class="card">
        <div class="visual-picker">
          <div>
            <span class="hint">本题演示</span>
            <b><math-text :text="spec.title" inline /></b>
          </div>
        </div>
        <math-text class="visual-goal" :text="spec.teaching_goal" inline />
        <visualization-canvas :spec="spec" :values="values" />
        <div v-for="variable in spec.interactive_variables" :key="variable.name" class="control">
          <div>
            <math-text :text="variable.label || variable.name" inline />
            <b>{{ values[variable.name] }}</b>
          </div>
          <WebSlider
            :value="values[variable.name]"
            :min="variable.min"
            :max="variable.max"
            :step="variable.step || 1"
            activeColor="var(--color-primary)"
            @changing="values[variable.name] = $event.detail.value"
            @change="values[variable.name] = $event.detail.value"
          />
        </div>
        <div class="task">
          <span>试一试</span>
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
        </div>
      </div>
      <div class="card">
        <span class="field-label">你发现了什么？</span>
        <WebTextarea
          v-model="observation"
          class="field-textarea"
          aria-label="图解观察"
          placeholder="写下图形或数值的变化"
        />
        <span v-if="!observation.trim()" class="disabled-help">先写下你的观察，再继续教学</span>
        <button
          role="button"
          class="primary-btn"
          :disabled="busy || !observation.trim() || !id"
          @click="save"
        >
          {{ busy ? '正在保存…' : '保存观察并返回' }}
        </button>
      </div>
    </div>
  </div>
</template>
<script setup>
import { browser } from '@/platform/browser.js'
import { go } from '@/utils/navigation.js'
import MathText from '@/components/math-text/math-text.vue'
import VisualizationCanvas from '@/components/visualization-canvas/visualization-canvas.vue'
import { reactive, ref } from 'vue'
import { onLoad } from '@/platform/lifecycle.js'
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
    browser.redirectTo({ url: `/pages/tutor/tutor?id=${id.value}` })
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
  padding: 12.0px;
  margin-bottom: 9.0px;
  border-radius: 11.0px;
  background: var(--color-primary-soft);
  border: 0.5px solid var(--color-primary-border);
}
.question-context span,
.question-context b {
  display: block;
}
.question-context span {
  font-size: 11.0px;
  color: var(--color-primary);
}
.question-context b {
  margin-top: 4.0px;
  font-size: 13.5px;
  line-height: 1.6;
  color: var(--color-text-primary);
  font-weight: 600;
}
.visual-picker {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10.0px;
  background: var(--color-primary-soft);
  border-radius: 9.0px;
  margin-bottom: 9.0px;
}
.visual-picker span,
.visual-picker b {
  display: block;
}
.visual-picker b {
  font-size: 14.5px;
  color: var(--color-primary);
  margin-top: 2.0px;
  font-weight: 600;
}
.visual-goal {
  display: block;
  color: var(--color-text-secondary);
  font-size: 12.0px;
  margin: 9.0px 0;
}
.control {
  margin-top: 12.0px;
}
.control > div {
  display: flex;
  justify-content: space-between;
  font-size: 12.0px;
}
.control b {
  color: var(--color-primary);
}
.control slider {
  margin: 2.5px 0;
}
.task {
  margin-top: 13.0px;
  padding: 11.0px;
  border-radius: 9.0px;
  background: var(--color-warning-soft);
}
.task span,
.task b,
.task small {
  display: block;
}
.task span {
  color: #9a6416;
  font-size: 11.0px;
}
.task b {
  margin-top: 3.5px;
  font-weight: 600;
}
.task small {
  color: #6f4a14;
  font-size: 10.5px;
  margin-top: 3.5px;
}
</style>
