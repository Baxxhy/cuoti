<template>
  <view class="task-visualization">
    <template v-if="visual">
      <view class="visual-heading">
        <math-text :text="visual.spec.title" inline />
        <button
          class="text-action"
          role="button"
          tabindex="0"
          :disabled="busy"
          @click="close"
          @keydown.enter.prevent="close"
        >
          收起图示
        </button>
      </view>
      <math-text :text="`原式：$${visual.source_equation_tex}$`" />
      <text class="muted">看图属于本次辅助学习。</text>
      <visualization-canvas
        :spec="visual.spec"
        :values="values"
        :canvas-id="`task-visual-${taskId}`"
      />
      <math-text class="muted" role="status" :text="controlSummary" inline />
      <view v-for="v in visual.spec.interactive_variables" :key="v.name" class="visual-control">
        <math-text :text="v.label + '：' + displayNumber(values[v.name])" inline />
        <view class="control-buttons">
          <button
            class="text-action"
            role="button"
            tabindex="0"
            :aria-label="`减小${v.label}`"
            :disabled="busy || values[v.name] <= v.min"
            @click="change(v, -1)"
            @keydown.enter.prevent="change(v, -1)"
          >
            减小
          </button>
          <button
            class="text-action"
            role="button"
            tabindex="0"
            :aria-label="`增大${v.label}`"
            :disabled="busy || values[v.name] >= v.max"
            @click="change(v, 1)"
            @keydown.enter.prevent="change(v, 1)"
          >
            增大
          </button>
        </view>
      </view>
      <text v-if="conflict" class="muted" role="alert">
        图示记录已有更新。草稿已保留，请先核对当前步骤与已保存内容。
      </text>
      <view v-if="conflict && visual.observation" class="saved-observation">
        <text>已保存的观察：</text>
        <math-text :text="visual.observation" />
      </view>
      <button
        v-if="conflict"
        class="text-action"
        role="button"
        tabindex="0"
        @keydown.enter.prevent="reset"
        @click="reset"
      >
        使用已保存的记录
      </button>
      <button
        v-if="conflict"
        class="text-action"
        role="button"
        :disabled="busy"
        tabindex="0"
        @keydown.enter.prevent="confirmDraft"
        @click="confirmDraft"
      >
        核对后使用草稿
      </button>
      <text class="field-label">你观察到了什么？</text>
      <view ref="inputContainer">
        <textarea
          v-model="observation"
          aria-label="图示观察"
          :maxlength="1200"
          :disabled="busy"
          auto-height
        />
      </view>
      <text class="muted">记录自己的观察，接着用作答确认。</text>
      <button
        class="primary-btn"
        role="button"
        tabindex="0"
        :disabled="busy || conflict || !observation.trim()"
        @click="save"
        @keydown.enter.prevent="save"
      >
        保存观察
      </button>
      <text v-if="savedMatches" class="muted" role="status">已保存这次观察。</text>
      <text v-if="notice" class="muted" role="status">{{ notice }}</text>
    </template>
    <template v-else>
      <text class="muted" role="alert">这张图暂时无法显示，可以继续文字作答。</text>
      <button class="text-action" role="button" @click="close">收起图示</button>
    </template>
  </view>
</template>
<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import MathText from '@/components/math-text/math-text.vue'
import VisualizationCanvas from '@/components/visualization-canvas/visualization-canvas.vue'
import { parseTaskVisualization } from '@/visualizations/task-visualization'
import { readTaskDraft, saveTaskDraft } from '@/utils/task-draft.js'
import { useAppStore } from '@/store/index.js'
const props = defineProps({
  packet: Object,
  taskId: String,
  fingerprint: String,
  stepId: String,
  busy: Boolean,
})
const emit = defineEmits(['save', 'close'])
const store = useAppStore(),
  inputContainer = ref(null)
const visual = computed(() => {
  try {
    return parseTaskVisualization(props.packet)
  } catch {
    return null
  }
})
const values = ref({}),
  observation = ref(''),
  conflict = ref(false),
  notice = ref('')
const scope = () =>
  JSON.stringify([props.fingerprint, visual.value?.source_phase, visual.value?.source_equation_tex])
const valueSignature = (v, text) =>
  JSON.stringify([
    visual.value?.spec.interactive_variables.map((item) => [item.name, v?.[item.name]]),
    text,
  ])
const signature = () => valueSignature(visual.value?.values, visual.value?.observation)
const draftKey = () => `visual:${props.taskId}`
let baseSignature = '',
  draftStep = ''
function remember() {
  if (
    visual.value &&
    !saveTaskDraft(store.user?.id, draftKey(), {
      fingerprint: scope(),
      step_id: draftStep,
      values: { ...values.value },
      text: observation.value,
      server_signature: baseSignature,
    })
  )
    notice.value = '本机暂时无法保存草稿，请在离开前保存观察。'
}
function load() {
  if (!visual.value) return
  const draft = readTaskDraft(store.user?.id, draftKey(), scope())
  draftStep = draft.values ? draft.step_id || '' : props.stepId
  baseSignature = draft.server_signature || signature()
  try {
    if (draft.values) parseTaskVisualization({ ...visual.value, values: draft.values })
    values.value = { ...(draft.values || visual.value.values) }
  } catch {
    values.value = { ...visual.value.values }
  }
  observation.value =
    draft.values && typeof draft.text === 'string' ? draft.text : visual.value.observation
  conflict.value =
    (draftStep !== props.stepId || baseSignature !== signature()) &&
    valueSignature(values.value, observation.value) !== signature()
  if (!conflict.value) {
    baseSignature = signature()
    draftStep = props.stepId
  }
}
function reset() {
  if (props.busy || !visual.value) return
  values.value = { ...visual.value.values }
  observation.value = visual.value.observation
  baseSignature = signature()
  draftStep = props.stepId
  conflict.value = false
  remember()
}
function confirmDraft() {
  if (props.busy) return
  draftStep = props.stepId
  baseSignature = signature()
  conflict.value = false
  remember()
}
function change(v, direction) {
  if (props.busy) return
  values.value[v.name] = Math.min(
    v.max,
    Math.max(
      v.min,
      v.min + (Math.round((values.value[v.name] - v.min) / v.step) + direction) * v.step,
    ),
  )
  remember()
}
function save() {
  if (!props.busy && !conflict.value && observation.value.trim() && visual.value)
    emit('save', { values: { ...values.value }, text: observation.value })
}
function close() {
  if (!props.busy) emit('close')
}
function displayNumber(value) {
  const short = Number(Number(value).toPrecision(7))
  return short === value ? String(value) : `约${short}`
}
const controlSummary = computed(() => {
  if (!visual.value) return ''
  if (visual.value.spec.type === 'equation_balance')
    return `等式两边同时减去${values.value.delta}，两边执行相同运算。`
  return (
    '当前图像参数：' +
    visual.value.spec.interactive_variables
      .map((v) => `${v.label}${displayNumber(values.value[v.name])}`)
      .join('，') +
    (visual.value.spec.type === 'quadratic_function' && values.value.a === 0
      ? '。a为0，此时不再是二次函数。'
      : visual.value.spec.type === 'linear_function' && values.value.k === 0
        ? '。k为0，此时不再是一次函数。'
        : '。参数改动后是对照图。')
  )
})
const savedMatches = computed(
  () =>
    visual.value?.observation && valueSignature(values.value, observation.value) === signature(),
)
function labelInput() {
  // #ifdef H5
  const root = inputContainer.value?.$el || inputContainer.value
  root?.querySelector?.('textarea')?.setAttribute('aria-label', '图示观察')
  // #endif
}
watch(() => [props.packet, props.stepId], load, { immediate: true })
watch(observation, remember)
watch([visual, inputContainer], () => nextTick(labelInput), { flush: 'post' })
onMounted(() => nextTick(labelInput))
</script>
<style scoped lang="scss">
.task-visualization {
  margin: 16px 0;
  padding: 16px 0;
  border-top: 1px solid var(--color-border);
  border-bottom: 1px solid var(--color-border);
}
.visual-heading,
.visual-control,
.control-buttons {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}
.visual-heading {
  font-size: 18px;
  font-weight: 600;
}
.visual-control {
  font-size: 16px;
  line-height: 1.6;
}
.muted {
  display: block;
  font-size: 14px;
  line-height: 1.6;
  color: var(--color-text-secondary);
  margin: 8px 0;
}
.text-action {
  margin: 0;
  min-height: 48px;
  padding: 12px 0;
  background: transparent;
  color: var(--color-primary);
  font-size: 14px;
}
.field-label {
  display: block;
  font-size: 16px;
  margin: 16px 0 8px;
}
textarea {
  width: 100%;
  min-height: 72px;
  padding: 12px;
  border: 1px solid var(--color-border);
  border-radius: 12px;
  background: var(--color-surface);
  font-size: 16px;
  line-height: 1.6;
}
.primary-btn {
  margin-top: 16px;
}
.saved-observation {
  font-size: 16px;
  line-height: 1.6;
}
</style>
