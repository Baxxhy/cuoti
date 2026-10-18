<template>
  <view class="written-answer">
    <textarea
      :value="modelValue"
      :disabled="uploading || disabled"
      auto-height
      maxlength="1200"
      :placeholder="placeholder"
      @input="emit('update:modelValue', $event.detail.value)"
    />
    <textarea
      v-if="showWorking"
      :value="working"
      :disabled="uploading || disabled"
      class="working"
      auto-height
      maxlength="800"
      placeholder="关键步骤（可不填）"
      @input="emit('update:working', $event.detail.value)"
    />
    <view v-if="allowHandwriting" class="handwriting-area">
      <view class="heading">
        <view>
          <b>手写过程</b>
          <text>可以直接拍照，识别后仍可修改文字</text>
        </view>
        <button v-if="!imageUrl" :disabled="uploading || disabled" @click="choose">
          {{ uploading ? '正在识别…' : '拍照或选图' }}
        </button>
      </view>
      <view v-if="uploading" class="parsing">
        <view>
          <b>{{ phase }}</b>
          <text>{{ Math.round(progress) }}%</text>
        </view>
        <view class="track"><view :style="{ width: `${progress}%` }" /></view>
        <text>正在解析手写答案和关键步骤，请稍候…</text>
      </view>
      <view v-if="imageUrl" class="preview">
        <image :src="imageUrl" mode="widthFix" />
        <view>
          <text>{{ status }}</text>
          <button :disabled="uploading || disabled" @click="choose">重新拍摄</button>
          <button :disabled="uploading || disabled" @click="reset">移除</button>
        </view>
      </view>
      <text v-if="notice" class="upload-notice" role="status">{{ notice }}</text>
    </view>
  </view>
</template>

<script setup>
import { onBeforeUnmount, ref } from 'vue'
import { uploadFile } from '@/api/index.js'

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
let active = true,
  timer

function notify() {
  emit('handwriting-change', { image_url: imageUrl.value, recognition: recognition.value })
}
function reset() {
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
    if (answer) emit('update:modelValue', answer)
    if (steps.length) emit('update:working', steps.join('\n'))
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
  uni.chooseImage({
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
  if (uploading.value || !active) return
  imageUrl.value = value?.image_url || ''
  recognition.value = value?.recognition || null
  status.value = imageUrl.value ? '已恢复作答照片，请核对文字后提交' : ''
  notify()
}
defineExpose({ reset, restore })
</script>

<style scoped lang="scss">
.written-answer > textarea {
  width: 100%;
  min-height: 170rpx;
  padding: 20rpx;
  border: 1rpx solid var(--color-border);
  border-radius: 16rpx;
  background: var(--color-surface-subtle);
  font-size: 27rpx;
  line-height: 1.65;
}
.written-answer > .working {
  min-height: 104rpx;
  margin-top: 14rpx;
  background: #fff;
}
.handwriting-area {
  margin-top: 16rpx;
  padding: 18rpx;
  border: 1rpx dashed var(--color-primary-border);
  border-radius: 14rpx;
  background: var(--color-primary-soft);
}
.heading {
  display: flex;
  align-items: center;
  gap: 16rpx;
}
.heading > view {
  flex: 1;
  min-width: 0;
}
.heading b,
.heading text {
  display: block;
}
.heading text {
  margin-top: 3rpx;
  color: var(--color-text-secondary);
  font-size: 20rpx;
}
.heading button,
.preview button {
  min-height: 60rpx;
  margin: 0;
  padding: 0 16rpx;
  border: 1rpx solid var(--color-primary-border);
  border-radius: 11rpx;
  background: #fff;
  color: var(--color-primary-hover);
  font-size: 21rpx;
}
.parsing {
  margin-top: 16rpx;
  padding: 16rpx;
  border-radius: 12rpx;
  background: #fff;
}
.parsing > view:first-child,
.preview > view {
  display: flex;
  align-items: center;
  gap: 10rpx;
  justify-content: space-between;
}
.track {
  height: 10rpx;
  margin-top: 12rpx;
  overflow: hidden;
  border-radius: 999rpx;
  background: #dce7ff;
}
.track > view {
  height: 100%;
  background: var(--color-primary);
}
.parsing > text {
  display: block;
  margin-top: 10rpx;
  color: var(--color-text-secondary);
  font-size: 19rpx;
}
.preview image {
  display: block;
  width: 100%;
  max-height: 420rpx;
  margin: 14rpx 0;
  border-radius: 10rpx;
}
.preview text {
  flex: 1;
  color: var(--color-text-secondary);
  font-size: 20rpx;
}
.upload-notice {
  display: block;
  margin-top: 12rpx;
  color: var(--color-text-secondary);
  font-size: 23rpx;
  line-height: 1.6;
}
</style>
