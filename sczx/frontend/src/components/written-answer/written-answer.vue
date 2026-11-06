<template>
  <div class="written-answer">
    <WebTextarea
      :value="modelValue"
      :disabled="uploading || disabled"
      auto-height
      maxlength="1200"
      :placeholder="placeholder"
      aria-label="我的作答"
      :cursor="answerCursor"
      :focus="answerFocus"
      @input="onInput"
      @blur="rememberCursor"
    />
    <WebTextarea
      v-if="showWorking"
      :value="working"
      :disabled="uploading || disabled"
      class="working"
      auto-height
      maxlength="800"
      aria-label="解题步骤"
      placeholder="关键步骤（可不填）"
      @input="emit('update:working', $event.detail.value)"
    />
    <div v-if="allowHandwriting" class="handwriting-area">
      <div class="heading">
        <button role="button" v-if="!imageUrl" :disabled="uploading || disabled" @click="choose">
          <WebIcon type="camera" size="19" color="currentColor" aria-hidden="true" />
          {{ uploading ? '正在识别…' : '拍照上传作答' }}
        </button>
      </div>
      <div v-if="uploading" class="parsing">
        <div>
          <b>{{ phase }}</b>
          <span>{{ Math.round(progress) }}%</span>
        </div>
        <div class="track"><div :style="{ width: `${progress}%` }" /></div>
        <span>正在解析手写答案和关键步骤，请稍候…</span>
      </div>
      <div v-if="imageUrl" class="preview">
        <WebImage :src="imageUrl" mode="widthFix" />
        <div>
          <span>{{ status }}</span>
          <button role="button" :disabled="uploading || disabled" @click="choose">重新拍摄</button>
          <button role="button" :disabled="uploading || disabled" @click="reset">移除</button>
        </div>
      </div>
      <span v-if="notice" class="upload-notice" role="status">{{ notice }}</span>
      <div v-if="suggestedAnswer" class="recognition-suggestion">
        <span>识别结果</span>
        <math-text :text="suggestedAnswer" />
        <span class="suggestion-caption">已填写的作答保留在输入框中。</span>
        <div>
          <button role="button" :disabled="disabled || uploading" @click="acceptRecognition">
            使用识别文字
          </button>
          <button role="button" :disabled="disabled || uploading" @click="dismissRecognition">
            保留我的作答
          </button>
        </div>
      </div>
    </div>
    <div class="math-tools">
      <button
        role="button"
        :disabled="uploading || disabled"
        :aria-expanded="symbolsOpen"
        @click="symbolsOpen = !symbolsOpen"
      >
        数学符号
      </button>
      <div v-if="symbolsOpen" class="math-keys">
        <button
          v-for="key in mathKeys"
          :key="key.label"
          role="button"
          :disabled="uploading || disabled"
          @click="insertSymbol(key)"
        >
          {{ key.label }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { browser } from '@/platform/browser.js'
import { nextTick, onBeforeUnmount, ref } from 'vue'
import { uploadFile } from '@/api/index.js'
import { mathKeys, insertMathText } from '@/utils/math-input.js'

const props = defineProps({
  modelValue: { type: String, default: '' },
  working: { type: String, default: '' },
  placeholder: { type: String, default: '写下答案和关键步骤' },
  showWorking: Boolean,
  allowHandwriting: { type: Boolean, default: true },
  uploadUrl: { type: String, default: '' },
  uploadData: { type: Object, default: () => ({}) },
  finalAnswerOnly: Boolean,
  disabled: Boolean,
})
const emit = defineEmits([
  'update:modelValue',
  'update:working',
  'handwriting-change',
  'uploading-change',
])
const imageUrl = ref(''),
  recognition = ref(null),
  status = ref(''),
  notice = ref('')
const uploading = ref(false),
  progress = ref(0),
  phase = ref('准备照片')
const suggestedAnswer = ref(''),
  suggestedWorking = ref(''),
  symbolsOpen = ref(false),
  answerCursor = ref(-1),
  answerFocus = ref(false)
let cursor = null
function onInput(event) {
  const position = event.detail?.cursor ?? event.target?.selectionStart
  cursor = Number.isInteger(position) ? position : null
  emit('update:modelValue', event.detail?.value ?? event.target?.value ?? '')
}
function rememberCursor(event) {
  const position = event.detail?.cursor ?? event.target?.selectionStart
  if (Number.isInteger(position)) cursor = position
}
async function insertSymbol(key) {
  if (uploading.value || props.disabled) return
  const result = insertMathText(props.modelValue, key, cursor)
  if (!result) return
  answerFocus.value = false
  emit('update:modelValue', result.value)
  cursor = result.cursor
  await nextTick()
  answerCursor.value = result.cursor
  answerFocus.value = true
}
function acceptRecognition() {
  if (props.disabled || uploading.value || !suggestedAnswer.value) return
  emit('update:modelValue', suggestedAnswer.value)
  if (suggestedWorking.value) emit('update:working', suggestedWorking.value)
  suggestedAnswer.value = suggestedWorking.value = ''
}
function dismissRecognition() {
  suggestedAnswer.value = suggestedWorking.value = ''
}
let active = true,
  timer

function notify() {
  emit('handwriting-change', { image_url: imageUrl.value, recognition: recognition.value })
}
function reset() {
  suggestedAnswer.value = suggestedWorking.value = ''
  imageUrl.value = ''
  recognition.value = null
  status.value = ''
  notice.value = ''
  progress.value = 0
  phase.value = '准备照片'
  notify()
}
async function recognize({ tempFilePaths }) {
  const path = tempFilePaths?.[0]
  if (!path || !active) return
  uploading.value = true
  suggestedAnswer.value = suggestedWorking.value = ''
  notice.value = ''
  emit('uploading-change', true)
  progress.value = 8
  phase.value = '正在上传照片'
  timer = setInterval(() => {
    if (progress.value < 88) progress.value += progress.value < 55 ? 3 : 1
    if (progress.value >= 55) phase.value = '正在识别手写内容'
  }, 450)
  try {
    const data = await uploadFile(props.uploadUrl, path, 'file', props.uploadData, (value) => {
      if (active) progress.value = Math.max(progress.value, 8 + value * 0.47)
    })
    if (!active) return
    phase.value = '正在整理答案步骤'
    const parsed = data.recognition || {},
      steps = Array.isArray(parsed.steps) ? parsed.steps : []
    const finalAnswer = String(parsed.final_answer || '')
    const processParts = [...steps]
    // Recognition often repeats the final answer as its last working step.
    const lastStep = String(steps.at(-1) || '').replace(/\s/g, '')
    if (finalAnswer && lastStep !== finalAnswer.replace(/\s/g, '')) processParts.push(finalAnswer)
    const process = processParts.filter(Boolean).join('\n')
    const answer = props.finalAnswerOnly
      ? parsed.final_answer || parsed.transcription
      : process || parsed.transcription
    imageUrl.value = data.image_url
    recognition.value = parsed
    if (answer && (props.modelValue.trim() || props.working.trim())) {
      suggestedAnswer.value = answer
      suggestedWorking.value = steps.join('\n')
    } else {
      if (answer) emit('update:modelValue', answer)
      if (steps.length) emit('update:working', steps.join('\n'))
    }
    status.value = !answer
      ? '没有识别到可用文字'
      : parsed.uncertain
        ? '部分内容不清晰，请核对识别文字'
        : '已识别，请核对后提交'
    if (!answer) notice.value = '请重新拍摄清晰的作答照片，或直接填写文字。已填写的答案会保留。'
    progress.value = 100
    notify()
  } catch {
    if (active) notice.value = '识别没有完成，请重新选图或使用文字输入。已填写的答案会保留。'
  } finally {
    clearInterval(timer)
    if (active) {
      uploading.value = false
      emit('uploading-change', false)
    }
  }
}
function choose() {
  if (uploading.value || props.disabled || !props.uploadUrl) return
  browser.chooseImage({
    count: 1,
    sizeType: ['compressed'],
    sourceType: ['camera', 'album'],
    success: recognize,
  })
}
onBeforeUnmount(() => {
  active = false
  clearInterval(timer)
})
function restore(value) {
  suggestedAnswer.value = suggestedWorking.value = ''
  if (uploading.value || !active) return
  imageUrl.value = value?.image_url || ''
  recognition.value = value?.recognition || null
  status.value = imageUrl.value ? '已恢复作答照片，请核对文字后提交' : ''
  notify()
}
defineExpose({ reset, restore })
</script>

<style scoped lang="scss">
.math-tools {
  margin: 4px 0;
}
.math-tools > button {
  margin: 0;
  padding: 8px 0;
  min-height: 44px;
  font-size: 13px;
  text-align: left;
  background: transparent;
  color: var(--color-text-secondary);
}
.math-keys {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.math-keys button {
  min-height: 44px;
  min-width: 44px;
  margin: 0;
  padding: 8px 12px;
  background: var(--color-surface-subtle);
  color: var(--color-text-primary);
  font-size: 15px;
  border-radius: 8px;
}
.recognition-suggestion {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--color-border);
  font-size: 14px;
  line-height: 1.6;
}
.recognition-suggestion > span {
  display: block;
  margin: 6px 0;
}
.suggestion-caption {
  font-size: 13px;
  color: var(--color-text-secondary);
}
.recognition-suggestion > div {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.recognition-suggestion button {
  margin: 0;
  padding: 8px 10px;
  min-height: 44px;
  font-size: 14px;
  color: var(--color-primary);
  background: var(--color-surface);
}
.written-answer > .web-textarea {
  box-sizing: border-box;
  width: 100%;
  min-height: 104px;
  padding: 0.625rem;
  border: 0.03125rem solid var(--color-border);
  border-radius: 12px;
  background: var(--color-surface-subtle);
  font-size: 16px;
  line-height: 1.65;
}
.written-answer > .working {
  min-height: 3.25rem;
  margin-top: 0.4375rem;
  background: #fff;
}
.written-answer > .web-textarea:focus-within {
  border-color: var(--color-primary);
  outline: none;
  box-shadow: none;
}
.handwriting-area {
  margin-top: 0.5rem;
  padding: 0;
  border: 0;
  border-radius: 0.4375rem;
  background: transparent;
}
.heading {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.heading > div {
  flex: 1;
  min-width: 0;
}
.heading b,
.heading span {
  display: block;
}
.heading span {
  margin-top: 0.09375rem;
  color: var(--color-text-secondary);
  font-size: 0.625rem;
}
.heading button,
.preview button {
  display: flex;
  align-items: center;
  gap: 6px;
  min-height: 44px;
  margin: 0;
  padding: 0 0.5rem;
  border: 0;
  border-radius: 0.34375rem;
  background: #fff;
  color: var(--color-primary-hover);
  font-size: 14px;
}
.parsing {
  margin-top: 0.5rem;
  padding: 0.5rem;
  border-radius: 0.375rem;
  background: #fff;
}
.parsing > div:first-child,
.preview > div {
  display: flex;
  align-items: center;
  gap: 0.3125rem;
  justify-content: space-between;
  flex-wrap: wrap;
}
.track {
  height: 0.3125rem;
  margin-top: 0.375rem;
  overflow: hidden;
  border-radius: 31.21875rem;
  background: #dce7ff;
}
.track > div {
  height: 100%;
  background: var(--color-primary);
}
.parsing > span {
  display: block;
  margin-top: 0.3125rem;
  color: var(--color-text-secondary);
  font-size: 0.59375rem;
}
.preview img {
  display: block;
  width: 100%;
  max-height: 13.125rem;
  margin: 0.4375rem 0;
  border-radius: 0.3125rem;
}
.preview span {
  flex: 1;
  color: var(--color-text-secondary);
  font-size: 0.625rem;
}
.upload-notice {
  display: block;
  margin-top: 0.375rem;
  color: var(--color-text-secondary);
  font-size: 0.71875rem;
  line-height: 1.6;
}
</style>
