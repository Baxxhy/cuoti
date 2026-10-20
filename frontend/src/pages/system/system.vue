<template>
  <view class="page">
    <app-header title="系统与智能服务" back />
    <view class="page-content">
      <state-panel v-if="!provider" :state="error ? 'error' : 'loading'" @retry="load" />
      <template v-else>
        <view
          class="system-status"
          :class="{ warn: ['unavailable', 'degraded'].includes(provider.last_status) }"
        >
          <view class="pulse" />
          <view>
            <text>智能服务</text>
            <b>{{ statusLabel }}</b>
          </view>
        </view>
        <view class="system-grid">
          <view>
            <b>{{ provider.text_entries }}</b>
            <text>对话线路</text>
          </view>
          <view>
            <b>{{ provider.vision_entries }}</b>
            <text>图片线路</text>
          </view>
          <view>
            <b>{{ provider.total_entries }}</b>
            <text>全部线路</text>
          </view>
        </view>
        <view class="section-title"><text>识别能力</text></view>
        <view class="capability-grid">
          <view>
            <uni-icons
              aria-hidden="true"
              :type="provider.vision_entries > 0 ? 'settings' : 'circle'"
              size="36"
              :color="
                provider.vision_entries > 0 ? 'var(--color-primary)' : 'var(--color-text-secondary)'
              "
            />
            <b>图片识别</b>
            <text>{{ provider.vision_entries > 0 ? '已配置' : '未配置' }}</text>
          </view>
        </view>
        <view class="section-title"><text>当前智能模型</text></view>
        <view class="card model-card">
          <text class="tag">逻辑模型</text>
          <b>{{ provider.logical_model }}</b>
          <text>文本和图片请求会在 CSU 可用线路之间依次轮询。</text>
          <view class="rotation">
            <text>文本位置 {{ provider.text_cursor ?? 0 }}</text>
            <text>图片位置 {{ provider.vision_cursor ?? 0 }}</text>
            <text>最近状态 {{ statusLabel }}</text>
          </view>
          <button role="button" class="primary-btn" :disabled="probing" @click="probe">
            {{ probing ? '正在检查线路…' : '重新检查智能服务' }}
          </button>
        </view>
        <view v-if="canConfigure" class="section-title"><text>App 本地联调地址</text></view>
        <view v-if="canConfigure" class="card">
          <text class="muted">仅开发包可修改。手机通过网关访问仓颉服务；H5 使用开发代理。</text>
          <view class="field">
            <input
              v-model="apiBase"
              class="field-input"
              placeholder="http://192.168.1.10:8002/api/v1"
            />
          </view>
          <button role="button" class="secondary-btn" @click="saveApi">保存 App 地址</button>
        </view>
      </template>
    </view>
  </view>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { getData, postData, setApiBase } from '@/api/index.js'
import { roleHome, useAppStore } from '@/store/index.js'
const store = useAppStore()
const canConfigure = import.meta.env.MODE !== 'production'
const provider = ref(null),
  error = ref(false),
  probing = ref(false)
const statusLabel = computed(
  () =>
    ({
      ok: '最近检查可用',
      degraded: '部分线路不可用',
      unavailable: '暂时不可用',
      idle: '尚未检查',
    })[provider.value?.last_status] || '状态待确认',
)
const apiBase = ref(
  uni.getStorageSync('minddimension_api_base') ||
    import.meta.env.VITE_API_BASE_URL ||
    'http://10.0.2.2:8002/api/v1',
)
async function load() {
  error.value = false
  try {
    await store.loadUser()
    if (store.role !== 'admin') {
      uni.reLaunch({ url: roleHome(store.role) })
      return
    }
    provider.value = await getData('/system/providers')
  } catch {
    error.value = true
  }
}
async function probe() {
  if (probing.value) return
  probing.value = true
  try {
    provider.value = await postData('/system/providers/probe', {})
  } catch {
  } finally {
    probing.value = false
  }
}
function saveApi() {
  try {
    apiBase.value = setApiBase(apiBase.value)
    uni.showToast({ title: '地址已保存', icon: 'success' })
  } catch (err) {
    uni.showToast({ title: err.message, icon: 'none' })
  }
}
onMounted(load)
</script>

<style scoped lang="scss">
.system-status {
  display: flex;
  align-items: center;
  gap: 20rpx;
  padding: 30rpx;
  border-radius: 24rpx;
  background: var(--color-surface);
  color: var(--color-text-primary);
}
.system-status.warn {
  background: var(--color-surface);
}
.system-status text,
.system-status b {
  display: block;
}
.system-status text {
  font-size: 22rpx;
  opacity: 0.7;
}
.system-status b {
  font-size: 34rpx;
  margin-top: 4rpx;
}
.pulse {
  width: 30rpx;
  height: 30rpx;
  border-radius: 50%;
  background: var(--color-primary);
}
.system-status.warn .pulse {
  background: var(--color-error);
}
.system-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 15rpx;
  margin-top: 20rpx;
}
.system-grid view {
  text-align: center;
  padding: 25rpx 8rpx;
  background: #fff;
  border-radius: 20rpx;
}
.system-grid b,
.system-grid text {
  display: block;
}
.system-grid b {
  font-size: 38rpx;
}
.system-grid text {
  font-size: 21rpx;
  color: #94a3b8;
}
.capability-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12rpx;
}
.capability-grid view {
  text-align: center;
  padding: 22rpx 8rpx;
  background: #fff;
  border-radius: 18rpx;
}
.capability-grid b,
.capability-grid text {
  display: block;
}
.capability-grid b {
  font-size: 23rpx;
  margin-top: 8rpx;
}
.capability-grid text {
  font-size: 18rpx;
  color: #94a3b8;
  margin-top: 4rpx;
}
.model-card > b,
.model-card > text {
  display: block;
}
.model-card > b {
  font-size: 34rpx;
  margin-top: 18rpx;
  color: #0f172a;
}
.model-card > text:nth-child(3) {
  color: #64748b;
  font-size: 23rpx;
  margin-top: 8rpx;
}
.rotation {
  display: flex;
  gap: 10rpx;
  flex-wrap: wrap;
  margin-top: 20rpx;
}
.rotation text {
  padding: 9rpx 15rpx;
  background: #f1f5f9;
  border-radius: 10rpx;
  color: #64748b;
  font-size: 20rpx;
}
</style>
