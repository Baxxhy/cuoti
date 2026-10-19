<template>
  <view class="page capture-page">
    <app-header title="录入错题" />
    <view class="page-content">
      <button
        role="button"
        class="capture-zone"
        :class="{ 'capture-zone-selected': imagePath }"
        :disabled="busy"
        aria-label="选择错题图片"
        @click="choose"
      >
        <template v-if="imagePath">
          <image class="preview-image" :src="imagePath" mode="aspectFit" />
          <view class="preview-hint">
            <uni-icons aria-hidden="true" type="camera" size="18" color="#FFFFFF" />
            <text>重新选择图片</text>
          </view>
        </template>
        <template v-else>
          <uni-icons aria-hidden="true" type="camera" size="44" color="var(--color-primary)" />
          <text class="capture-title">添加图片</text>
        </template>
      </button>
      <button
        role="button"
        class="primary-btn capture-primary-btn"
        :disabled="busy"
        @click="imagePath ? upload() : choose()"
      >
        {{ busy ? '正在上传…' : imagePath ? '框选题目' : '拍照或选择图片' }}
      </button>
      <text
        v-if="status"
        class="upload-status"
        :class="{ error: status.includes('失败') }"
        role="status"
      >
        {{ status }}
      </text>
      <button
        class="manual-entry"
        role="button"
        aria-label="手动录入错题"
        :disabled="busy"
        @click="uni.navigateTo({ url: '/pages/manual/manual' })"
      >
        <uni-icons
          aria-hidden="true"
          type="compose"
          size="19"
          color="var(--color-text-secondary)"
        />
        <text class="manual-entry-label">手动录入</text>
        <uni-icons aria-hidden="true" type="right" size="16" color="var(--color-text-tertiary)" />
      </button>
      <text class="capture-note">请保留完整题目与原始作答。</text>
    </view>
    <tab-bar current="capture" />
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { uploadFile } from '@/api/index.js'

const imagePath = ref('')
const busy = ref(false)
const status = ref('')

function choose() {
  if (busy.value) {
    return
  }

  uni.chooseImage({
    count: 1,

    sizeType: ['original'],

    sourceType: ['camera', 'album'],

    success: (res) => {
      const path = res.tempFilePaths?.[0]

      if (!path) {
        status.value = '没有读取到照片，请重新拍摄'
        return
      }

      imagePath.value = path

      status.value = '图片已选好'
    },

    fail: () => {
      status.value = '没有选择照片，可以重新拍摄'
    },
  })
}

async function upload() {
  if (!imagePath.value || busy.value) {
    return
  }

  busy.value = true

  status.value = '正在保存图片…'

  try {
    const data = await uploadFile('/questions/ingest', imagePath.value, 'file', {
      defer_processing: 'true',
    })

    uni.redirectTo({
      url: `/pages/crop/crop?id=${data.question_id}`,
    })
  } catch (e) {
    status.value = '上传失败，请重新选择'

    busy.value = false
  }
}
</script>

<style scoped lang="scss">
.capture-page {
  min-height: 100vh;
  background: var(--color-bg);
  color: var(--color-text-primary);
}
.page-content {
  padding: 24px var(--space-page) 110px;
  box-sizing: border-box;
}
.capture-zone {
  position: relative;
  width: 100%;
  height: 220px;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  margin: 0;
  border: 1px dashed var(--color-primary-border);
  border-radius: 12px;
  background: var(--color-surface);
}
.capture-zone-selected {
  height: 240px;
  background: var(--color-surface-subtle);
}
.capture-title {
  display: block;
  margin-top: 12px;
  color: var(--color-text-primary);
  font-size: 17px;
  font-weight: 600;
  line-height: 1.5;
}
.capture-desc {
  display: block;
  margin-top: 6px;
  color: var(--color-text-secondary);
  font-size: 13px;
  line-height: 1.7;
}
.preview-image {
  width: 100%;
  height: 100%;
  background: var(--color-surface-subtle);
}
.preview-hint {
  position: absolute;
  right: 10px;
  bottom: 10px;
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 9px;
  border-radius: 4px;
  background: rgba(24, 24, 27, 0.78);
  color: #fff;
  font-size: 12px;
}
.capture-primary-btn {
  margin-top: 12px;
}
.upload-status {
  display: block;
  margin: 8px 0 0;
  color: var(--color-text-secondary);
  font-size: 12px;
  line-height: 1.6;
}
.upload-status.error {
  color: var(--color-error);
}
.manual-entry {
  display: grid;
  grid-template-columns: 24px minmax(0, 1fr) 20px;
  align-items: center;
  gap: 10px;
  width: 100%;
  min-height: 50px;
  margin: 11px 0 0;
  padding: 0;
  border-top: 0.5px solid var(--color-border);
  border-bottom: 0.5px solid var(--color-border);
  border-radius: 0;
  background: transparent;
  color: var(--color-text-primary);
  font-size: 14px;
  text-align: left;
}
.manual-entry-label {
  min-width: 0;
  text-align: left;
  line-height: 1.5;
  white-space: nowrap;
}
.manual-entry::after {
  border: 0;
}
.capture-tips {
  padding: 16px 0;
}
.capture-tips text {
  display: block;
  color: var(--color-text-secondary);
  font-size: 12px;
  line-height: 1.85;
}
.capture-tips .tips-heading {
  margin-bottom: 5px;
  color: var(--color-text-primary);
  font-weight: 500;
  font-size: 13px;
}
.capture-note {
  display: block;
  margin: 24px 0;
  text-align: center;
  font-size: 13px;
  color: var(--color-text-secondary);
}
</style>
