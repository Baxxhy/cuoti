<template>
  <view class="page">
    <app-header title="学生学习报告" back />
    <state-panel
      v-if="loading || error || !data"
      :state="error ? 'error' : 'loading'"
      :message="error"
      @retry="load"
    />
    <view v-else class="page-content">
      <student-report :data="data" />
      <button class="secondary-btn" :disabled="loading" @click="load">刷新报告</button>
    </view>
    <view v-if="denied" class="page-content">
      <button class="primary-btn" @click="go('/pages/guardian/home')">返回家长中心</button>
    </view>
  </view>
</template>
<script setup>
import { ref } from 'vue'
import { onLoad, onShow, onHide, onUnload } from '@dcloudio/uni-app'
import { getData } from '@/api/index.js'
import { go } from '@/utils/navigation.js'
const data = ref(null),
  error = ref(''),
  loading = ref(true),
  denied = ref(false)
let id = '',
  generation = 0
async function load() {
  const current = ++generation
  data.value = null
  loading.value = true
  error.value = ''
  denied.value = false
  try {
    const result = await getData(`/guardians/students/${id}/overview`, { silent: true })
    if (current === generation) data.value = result
  } catch (err) {
    if (current !== generation) return
    denied.value = err.statusCode === 403 || err.statusCode === 404
    error.value = denied.value
      ? '当前已无权查看这份报告，请返回家长中心核对关联。'
      : err.message || '报告暂时无法加载，请重试'
  } finally {
    if (current === generation) loading.value = false
  }
}
function clear() {
  generation++
  data.value = null
}
onLoad((q) => {
  id = q.id || ''
})
onShow(load)
onHide(clear)
onUnload(clear)
</script>
