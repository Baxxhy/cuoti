<template>
  <view ref="container" class="self-check">
    <button
      class="disclosure"
      :aria-expanded="open"
      @click="toggle"
      role="button"
      tabindex="0"
      @keydown.enter.prevent="toggle"
    >
      自检要点
      <text>{{ open ? '收起' : '记一句，下次提醒自己' }}</text>
    </button>
    <view v-if="open" class="note-content">
      <text v-if="loading" role="status">正在读取要点…</text>
      <view v-if="error" class="error-note" role="alert">
        <text>{{ error }}</text>
        <button
          class="text-action"
          :disabled="busy"
          @click="load"
          role="button"
          tabindex="0"
          @keydown.enter.prevent="load"
        >
          重新核对
        </button>
      </view>
      <template v-if="data">
        <text v-if="!data.source_current" class="muted">原题已更新，这条要点仅作历史提醒。</text>
        <view v-if="data.note" class="saved-note">
          <math-text :text="data.note.text" />
          <view class="note-actions">
            <button
              v-if="data.can_save && !editing"
              class="text-action"
              @click="edit"
              role="button"
              tabindex="0"
              @keydown.enter.prevent="edit"
            >
              编辑
            </button>
            <button
              class="text-action"
              :disabled="busy"
              @click="remove"
              role="button"
              tabindex="0"
              @keydown.enter.prevent="remove"
            >
              删除要点
            </button>
          </view>
        </view>
        <template v-if="editing && data.can_save">
          <text class="field-label">下次遇到这类题，我要先检查什么？</text>
          <textarea
            v-model="text"
            aria-label="自检要点"
            :maxlength="300"
            :disabled="busy"
            auto-height
          />
          <text class="muted">最多300字。这是自己的提醒，不作为掌握证明。</text>
          <button
            class="primary-btn"
            :disabled="busy || !text.trim()"
            @click="save"
            role="button"
            tabindex="0"
            @keydown.enter.prevent="save"
          >
            {{ busy ? '正在保存…' : '确认保存' }}
          </button>
          <button
            v-if="data.note"
            class="text-action"
            :disabled="busy"
            @click="cancelEdit"
            role="button"
            tabindex="0"
            @keydown.enter.prevent="cancelEdit"
          >
            取消编辑
          </button>
        </template>
        <text v-if="message" class="muted" role="status">{{ message }}</text>
      </template>
    </view>
  </view>
</template>
<script setup>
import { nextTick, onMounted, onUpdated, ref, watch } from 'vue'
import MathText from '@/components/math-text/math-text.vue'
import { getData, patchData, deleteData } from '@/api/index.js'
import { useAppStore } from '@/store/index.js'
import { readTaskDraft, saveTaskDraft } from '@/utils/task-draft.js'
const props = defineProps({ task: { type: Object, required: true } })
const store = useAppStore()
const container = ref(null)
function labelInput() {
  // #ifdef H5
  // uni-textarea keeps attrs on its wrapper; label the actual editable control too.
  const element = container.value?.$el || container.value
  const control = element?.querySelector?.('textarea')
  control?.setAttribute?.('aria-label', '自检要点')
  // #endif
}
onMounted(() => nextTick(labelInput))
onUpdated(() => nextTick(labelInput))
const open = ref(false),
  loading = ref(false),
  busy = ref(false),
  editing = ref(false)
const data = ref(null),
  text = ref(''),
  error = ref(''),
  message = ref('')
// uni-view renders slots in a child effect; parent updated alone misses a newly shown field.
watch([data, editing, busy, open], () => nextTick(labelInput), { flush: 'post' })
let epoch = 0
const path = () => `/learning-tasks/${props.task.id}/self-check`
const draftKey = () => `self-check:${props.task.id}`
function keepDraft(value = text.value) {
  return saveTaskDraft(store.user?.id, draftKey(), {
    fingerprint: props.task.input_fingerprint,
    text: value,
    serverVersion: data.value?.version,
  })
}
async function load() {
  const request = ++epoch
  loading.value = true
  error.value = ''
  try {
    const next = await getData(path(), { silent: true })
    if (request !== epoch) return
    data.value = next
    const draft = readTaskDraft(store.user?.id, draftKey(), props.task.input_fingerprint)
    if (!editing.value) {
      editing.value = !next.note && next.can_save
      text.value = draft.text || next.note?.text || ''
      if (draft.text) editing.value = next.can_save
    }
    if (draft.text && draft.serverVersion !== next.version) {
      message.value = '已保存的要点有更新。请对照上方内容，核对自己的草稿后再保存。'
    }
  } catch {
    if (request === epoch) error.value = '暂时无法读取要点，输入会保留。'
  } finally {
    if (request === epoch) loading.value = false
  }
}
function toggle() {
  open.value = !open.value
  if (open.value) load()
}
function edit() {
  if (busy.value) return
  text.value = data.value.note.text
  editing.value = true
  message.value = ''
}
function cancelEdit() {
  if (busy.value) return
  editing.value = false
  keepDraft('')
  error.value = ''
  message.value = ''
}
async function save() {
  if (busy.value || !text.value.trim() || !data.value?.can_save) return
  busy.value = true
  error.value = ''
  message.value = ''
  try {
    data.value = await patchData(
      path(),
      {
        text: text.value,
        version: data.value.version,
        confirmed: true,
        input_fingerprint: props.task.input_fingerprint,
      },
      { silent: true },
    )
    editing.value = false
    keepDraft('')
    message.value = '已保存'
  } catch (reason) {
    error.value =
      reason.statusCode === 409
        ? '要点或原题已更新，请重新核对；草稿已保留。'
        : '暂时未能确认保存结果，请重试；草稿已保留。'
  } finally {
    busy.value = false
  }
}
function remove() {
  if (busy.value) return
  uni.showModal({
    title: '删除这条自检要点？',
    content: '学习过程和原作答会保留。',
    confirmText: '删除',
    success: async ({ confirm }) => {
      if (!confirm || busy.value) return
      busy.value = true
      error.value = ''
      message.value = ''
      try {
        data.value = await deleteData(path(), {
          data: { version: data.value.version },
          silent: true,
        })
        editing.value = data.value.can_save
        text.value = ''
        keepDraft('')
        message.value = '已删除'
      } catch {
        error.value = '暂时未能确认删除结果，请重新核对。'
      } finally {
        busy.value = false
      }
    },
  })
}
watch(text, () => {
  if (editing.value && !keepDraft()) message.value = '本机暂时无法保存草稿，请在离开前确认保存。'
})
watch(
  () => [props.task.id, props.task.status],
  () => {
    if (open.value) load()
  },
)
</script>
<style scoped lang="scss">
.self-check {
  margin-top: 24px;
  border-top: 1px solid var(--color-border);
}
.disclosure {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
  min-height: 48px;
  padding: 12px 0;
  background: transparent;
  text-align: left;
  font-size: 16px;
  color: var(--color-primary);
}
.disclosure text,
.muted {
  display: block;
  font-size: 14px;
  line-height: 1.6;
  color: var(--color-text-secondary);
}
.note-content {
  padding: 12px 0;
}
.field-label {
  display: block;
  font-size: 16px;
  line-height: 1.6;
  margin: 12px 0;
}
textarea {
  width: 100%;
  min-height: 96px;
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
.saved-note {
  padding: 12px 0;
  font-size: 16px;
  line-height: 1.6;
}
.note-actions {
  display: flex;
  gap: 24px;
}
.text-action {
  min-height: 48px;
  padding: 12px 0;
  margin: 0;
  background: transparent;
  color: var(--color-primary);
  font-size: 14px;
}
.error-note {
  color: var(--color-error);
  font-size: 14px;
}
</style>
