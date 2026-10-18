<template>
  <view class="page crop-page">
    <app-header title="框选题目" subtitle="拖动四角调整识别范围" back />
    <view v-if="question" class="crop-content">
      <movable-area class="crop-stage">
        <image :src="original" mode="aspectFit" @load="onImageLoad" />
        <movable-view
          v-if="!pendingJob || cropBoxKnown"
          class="crop-box"
          direction="all"
          :disabled="resizing || busy || !!pendingJob || jobCancelled"
          :x="imageBounds.left + box.x * imageBounds.width"
          :y="imageBounds.top + box.y * imageBounds.height"
          :style="{
            width: box.w * imageBounds.width + 'px',
            height: box.h * imageBounds.height + 'px',
          }"
          @change="moveBox"
        >
          <view
            v-for="handle in handles"
            :key="handle.name"
            class="corner"
            :class="handle.className"
            @touchstart.stop="startResize(handle.name, $event)"
            @mousedown.stop.prevent="startMouseResize(handle.name, $event)"
            @touchmove.stop.prevent="resizeBox"
            @touchend.stop="endResize"
            @touchcancel.stop="endResize"
          />
        </movable-view>
      </movable-area>

      <view class="crop-panel">
        <button
          class="secondary-btn"
          :disabled="busy || !!pendingJob || jobCancelled"
          @click="Object.assign(box, { x: 0, y: 0, w: 1, h: 1 })"
        >
          选择整张图片
        </button>
        <button class="primary-btn" :disabled="busy" @click="submit">
          {{
            busy ? status : jobCancelled ? '返回错题本' : pendingJob ? '查看识别结果' : '开始识别'
          }}
        </button>
        <text v-if="message" class="processing-hint">{{ message }}</text>
        <text v-if="busy" class="processing-hint">
          {{
            elapsedSeconds < 18
              ? '正在识别文字和公式，通常需要 10～20 秒'
              : '图片仍在处理，稍后可回到此页查看结果'
          }}
        </text>
      </view>
    </view>
    <state-panel v-else :state="error ? 'error' : 'loading'" @retry="load" />
  </view>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { onLoad, onUnload } from '@dcloudio/uni-app'
import { getData, postData } from '@/api/index.js'
import { containedImageBounds, resizeCropBox } from '@/utils/crop'
import { waitForProcessingJob } from '@/utils/processing.js'

const id = ref('')
const question = ref(null)
const error = ref(false)
const busy = ref(false)
const resizing = ref(false)
const status = ref('正在识别…')
const message = ref('')
const pendingJob = ref('')
const jobCancelled = ref(false)
const cropBoxKnown = ref(true)
const elapsedSeconds = ref(0)
const sys = uni.getSystemInfoSync()
const stageHeight = Math.min(sys.windowHeight * 0.55, 520)
const imageBounds = reactive({ left: 0, top: 0, width: sys.windowWidth, height: stageHeight })
const box = reactive({ x: 0.04, y: 0.04, w: 0.92, h: 0.92 })
const handles = [
  { name: 'nw', className: 'lt' },
  { name: 'ne', className: 'rt' },
  { name: 'sw', className: 'lb' },
  { name: 'se', className: 'rb' },
]
const original = computed(
  () => question.value?.assets?.find((item) => item.kind === 'original')?.url || '',
)

let loading = false
let active = true
let timer
let resizeState = null

function moveBox(event) {
  if (
    resizing.value ||
    busy.value ||
    pendingJob.value ||
    jobCancelled.value ||
    !event.detail.source
  )
    return
  box.x = Math.max(0, Math.min(1 - box.w, (event.detail.x - imageBounds.left) / imageBounds.width))
  box.y = Math.max(0, Math.min(1 - box.h, (event.detail.y - imageBounds.top) / imageBounds.height))
}

function onImageLoad(event) {
  const imageWidth = event.detail.width || 1
  const imageHeight = event.detail.height || 1
  uni
    .createSelectorQuery()
    .select('.crop-stage')
    .boundingClientRect((rect) => {
      if (!rect) return
      Object.assign(
        imageBounds,
        containedImageBounds(rect.width, rect.height, imageWidth, imageHeight),
      )
    })
    .exec()
}

function startResize(handle, event) {
  if (busy.value || pendingJob.value || jobCancelled.value) return
  const touch =
    event.touches?.[0] ||
    event.changedTouches?.[0] ||
    (Number.isFinite(event.clientX) ? event : null)
  if (!touch) return
  resizing.value = true
  resizeState = {
    handle,
    clientX: touch.clientX,
    clientY: touch.clientY,
    box: { x: box.x, y: box.y, width: box.w, height: box.h },
  }
}

function resizeBox(event) {
  if (!resizeState) return
  const touch =
    event.touches?.[0] ||
    event.changedTouches?.[0] ||
    (Number.isFinite(event.clientX) ? event : null)
  if (!touch) return
  const dx = (touch.clientX - resizeState.clientX) / imageBounds.width
  const dy = (touch.clientY - resizeState.clientY) / imageBounds.height
  const initial = resizeState.box
  const point = {
    x: resizeState.handle.includes('w') ? initial.x + dx : initial.x + initial.width + dx,
    y: resizeState.handle.includes('n') ? initial.y + dy : initial.y + initial.height + dy,
  }
  const next = resizeCropBox(initial, resizeState.handle, point, 0.12)
  Object.assign(box, { x: next.x, y: next.y, w: next.width, h: next.height })
}

function startMouseResize(handle, event) {
  // #ifdef H5
  startResize(handle, event)
  if (resizeState) {
    window.addEventListener('mousemove', resizeBox)
    window.addEventListener('mouseup', endResize)
  }
  // #endif
}

function endResize() {
  // #ifdef H5
  window.removeEventListener('mousemove', resizeBox)
  window.removeEventListener('mouseup', endResize)
  // #endif
  resizeState = null
  resizing.value = false
}

function restoreProcessingState(data) {
  question.value = data
  if (data.status === 'archived') {
    jobCancelled.value = true
    message.value = '题目已归档，请返回错题本'
    return false
  }
  const savedBox = data.crop_box
  if (Array.isArray(savedBox) && savedBox.length === 4) {
    Object.assign(box, { x: savedBox[0], y: savedBox[1], w: savedBox[2], h: savedBox[3] })
  }
  const job = data.processing_job
  if (!job || !['pending', 'running'].includes(job.status)) return false
  pendingJob.value = job.id
  cropBoxKnown.value = Array.isArray(savedBox) && savedBox.length === 4
  return true
}

async function load() {
  if (loading) return
  loading = true
  error.value = false
  try {
    const data = await getData(`/questions/${id.value}`)
    if (!active) return
    const resume = restoreProcessingState(data)
    if (resume && !busy.value) await submit()
  } catch {
    if (active) error.value = true
  } finally {
    loading = false
  }
}

async function submit() {
  if (busy.value) return
  if (jobCancelled.value) return uni.redirectTo({ url: '/pages/problem/list' })
  busy.value = true
  message.value = ''
  status.value = '正在识别…'
  elapsedSeconds.value = 0
  timer = setInterval(() => (elapsedSeconds.value += 1), 1000)
  try {
    if (!pendingJob.value) {
      try {
        const result = await postData(
          `/questions/${id.value}/crop`,
          {
            box: [box.x, box.y, Math.min(box.w, 1 - box.x), Math.min(box.h, 1 - box.y)],
          },
          { silent: true },
        )
        pendingJob.value = result.job_id
        cropBoxKnown.value = true
      } catch (requestError) {
        if (requestError.statusCode !== 409) throw requestError
        const current = await getData(`/questions/${id.value}`)
        if (!restoreProcessingState(current)) throw requestError
      }
    }
    const completed = await waitForProcessingJob(pendingJob.value, {
      getJob: (value) => getData(`/jobs/${value}`),
      isActive: () => active,
      onProgress: (job) => {
        status.value =
          job.progress < 35
            ? '正在优化图片…'
            : job.progress < 85
              ? '正在识别文字和公式…'
              : '正在整理识别结果…'
      },
    })
    if (completed && active) {
      const current = await getData(`/questions/${id.value}`)
      if (!active) return
      pendingJob.value = ''
      question.value = current
      if (current.status === 'awaiting_crop') {
        cropBoxKnown.value = true
        message.value = '图片已准备好，请选择识别范围'
      } else {
        uni.redirectTo({ url: `/pages/ocr/ocr?id=${id.value}` })
      }
    }
  } catch (err) {
    if (err.jobFailed) pendingJob.value = ''
    if (err.jobCancelled) jobCancelled.value = true
    message.value = err.message || '识别暂时中断，请重试'
  } finally {
    busy.value = false
    if (timer) clearInterval(timer)
  }
}

onLoad((query) => {
  id.value = query.id
  load()
})
onUnload(() => {
  endResize()
  active = false
  if (timer) clearInterval(timer)
})
</script>

<style scoped lang="scss">
.crop-content {
  padding-bottom: 30rpx;
}
.crop-stage {
  width: 100%;
  height: 55vh;
  max-height: 1040rpx;
  background: #10241d;
  position: relative;
  overflow: hidden;
  touch-action: none;
}
.crop-stage image {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}
.crop-box {
  border: 5rpx solid #f59e0b;
  background: rgba(245, 158, 11, 0.05);
  box-shadow: 0 0 0 2000rpx rgba(0, 0, 0, 0.52);
}
.corner {
  position: absolute;
  width: 76rpx;
  height: 76rpx;
  background: transparent;
  touch-action: none;
}
.corner:after {
  content: '';
  position: absolute;
  left: 50%;
  top: 50%;
  width: 30rpx;
  height: 30rpx;
  transform: translate(-50%, -50%);
  border-radius: 50%;
  background: #f59e0b;
  border: 5rpx solid #fff;
  box-sizing: border-box;
}
.lt {
  left: -38rpx;
  top: -38rpx;
}
.rt {
  right: -38rpx;
  top: -38rpx;
}
.lb {
  left: -38rpx;
  bottom: -38rpx;
}
.rb {
  right: -38rpx;
  bottom: -38rpx;
}
.crop-panel {
  margin: -10rpx 24rpx 0;
  padding: 28rpx 30rpx 30rpx;
  background: #fff;
  border-radius: 28rpx;
  position: relative;
  z-index: 2;
  box-shadow: 0 8rpx 30rpx rgba(0, 0, 0, 0.1);
}
.crop-help {
  display: block;
  text-align: center;
  color: var(--color-text-secondary);
  font-size: 24rpx;
}
.processing-hint {
  display: block;
  margin-top: 16rpx;
  text-align: center;
  color: var(--color-text-secondary);
  font-size: 22rpx;
}
</style>
