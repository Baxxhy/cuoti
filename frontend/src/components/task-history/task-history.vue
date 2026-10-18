<template>
  <view class="task-history">
    <button
      class="disclosure"
      :aria-expanded="open"
      @click="toggle"
      role="button"
      tabindex="0"
      @keydown.enter.prevent="toggle"
    >
      之前的过程
      <text>{{ open ? '收起' : '展开' }}</text>
    </button>
    <view v-if="open">
      <text v-if="loading" class="muted" role="status">正在读取记录…</text>
      <view v-if="error" role="alert">
        <text>{{ error }}</text>
        <button
          class="disclosure"
          @click="load"
          role="button"
          tabindex="0"
          @keydown.enter.prevent="load"
        >
          重新读取
        </button>
      </view>
      <view v-if="sourceQuestion && !error">
        <button
          class="disclosure"
          role="button"
          :aria-expanded="sourceOpen"
          tabindex="0"
          @keydown.enter.prevent="sourceOpen = !sourceOpen"
          @click="sourceOpen = !sourceOpen"
        >
          本次学习的题目 {{ sourceOpen ? '收起' : '查看' }}
        </button>
        <view v-if="sourceOpen">
          <math-text :text="sourceQuestion.question_text" />
          <view v-for="option in sourceQuestion.options || []" :key="option.label">
            <math-text :text="`${option.label}．${option.text}`" />
          </view>
          <text class="muted">
            {{
              sourceQuestion.origin === 'created'
                ? '保留开始学习时的题目。'
                : '旧任务来源已按原题版本重新核对。'
            }}
          </text>
        </view>
      </view>
      <text v-if="!loading && !items.length && !error" class="muted">提交后，这里会留下过程。</text>
      <view v-for="item in items" :key="item.id" class="event">
        <text class="event-heading">
          {{ kindLabel(item.kind) }}
          <text class="muted">{{ phaseLabel(item.phase) }}</text>
        </text>
        <teaching-content v-if="item.text" :blocks="[{ kind: 'text', text: item.text }]" />
        <view v-if="item.source?.student_step_id" class="source-step">
          <text class="muted">对应原作答第{{ item.source.step_index + 1 }}步</text>
          <math-text :text="item.source.student_step_text" />
        </view>
        <text class="muted">{{ statusLabel(item) }}</text>
        <teaching-content v-if="item.feedback" :blocks="[{ kind: 'text', text: item.feedback }]" />
        <view v-if="item.visualization" class="visual-record">
          <text>{{ item.visualization.title }}</text>
          <math-text :text="`$${item.visualization.relation_tex}$`" />
          <text class="muted">{{ item.visualization.controls }}</text>
        </view>
        <button
          v-if="item.handwriting_image_url"
          class="disclosure"
          role="button"
          tabindex="0"
          @click="preview(item.id)"
          @keydown.enter.prevent="preview(item.id)"
        >
          查看当时的照片
        </button>
      </view>
      <text v-if="hasMore" class="muted">仅显示最近50条动作。</text>
    </view>
  </view>
</template>
<script setup>
import { ref, watch } from 'vue'
import { getData } from '@/api/index.js'
import TeachingContent from '@/components/teaching-content/teaching-content.vue'
const props = defineProps({ task: { type: Object, required: true } })
const open = ref(false),
  loading = ref(false),
  error = ref(''),
  items = ref([]),
  hasMore = ref(false),
  sourceQuestion = ref(null),
  sourceOpen = ref(false)
let epoch = 0
async function load() {
  const request = ++epoch
  loading.value = true
  error.value = ''
  try {
    const data = await getData(`/learning-tasks/${props.task.id}/history`, { silent: true })
    if (request !== epoch) return
    items.value = [...data.items].reverse()
    hasMore.value = data.has_more
    sourceQuestion.value = data.source_question || null
  } catch {
    if (request === epoch) error.value = '暂时无法读取过程，已保存的回答仍在。'
  } finally {
    if (request === epoch) loading.value = false
  }
}
function toggle() {
  open.value = !open.value
  if (open.value) load()
}
async function preview(id) {
  await load()
  if (error.value) return
  const url = items.value.find((item) => item.id === id)?.handwriting_image_url
  if (url) uni.previewImage({ urls: [url], current: url })
}
const kindLabel = (kind) =>
  ({
    answer: '这次作答',
    hint: '请求提示',
    reveal: '查看参考答案',
    resume: '继续核对',
    use_text: '改用文字作答',
    visualize: '用图看看',
    observe_visualization: '记录图示观察',
    close_visualization: '收起图示',
    recognize_handwriting: '识别作答照片',
  })[kind] || '学习动作'
const phaseLabel = (phase) =>
  ({ repair: '局部订正', independent: '原题独立作答', contrast: '条件对照' })[phase] || ''
function statusLabel(item) {
  if (item.status !== 'applied')
    return (
      { pending: '正在核对', failed: '未完成核对', cancelled: '本次已结束', stale: '原题已更新' }[
        item.status
      ] || '记录已保存'
    )
  const verdict =
    {
      confirmed_correct: '本次结果已核对',
      confirmed_incorrect: '本次仍需订正',
      needs_review: '仍需核对',
      review_required: '仍需核对',
      probably_correct: '可能正确，仍需核对',
      probably_incorrect: '可能有误，仍需核对',
    }[item.verdict] || '已记录'
  return verdict + (item.assisted ? ' · 使用过辅助' : '')
}
watch(
  () => [props.task.id, props.task.version],
  () => {
    if (open.value && !['queued', 'running'].includes(props.task.status)) load()
  },
)
</script>
<style scoped lang="scss">
.task-history {
  margin-top: 24px;
  border-top: 1px solid var(--color-border);
}
.disclosure {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
  min-height: 48px;
  padding: 12px 0;
  background: transparent;
  text-align: left;
  color: var(--color-primary);
  font-size: 16px;
}
.event {
  padding: 16px 0;
  border-top: 1px solid var(--color-border);
}
.event-heading {
  display: block;
  font-size: 16px;
  line-height: 1.6;
}
.muted {
  font-size: 14px;
  line-height: 1.6;
  color: var(--color-text-secondary);
}
</style>
