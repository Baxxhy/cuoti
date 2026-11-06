<template>
  <div class="page">
    <app-header title="系统与智能服务" back />
    <div class="page-content">
      <state-panel v-if="!provider" :state="error ? 'error' : 'loading'" @retry="load" />
      <template v-else>
        <div
          class="system-status"
          :class="{ warn: ['unavailable', 'degraded'].includes(provider.last_status) }"
        >
          <div class="pulse" />
          <div>
            <span>智能服务</span>
            <b>{{ statusLabel }}</b>
          </div>
        </div>
        <div class="system-grid">
          <div>
            <b>{{ provider.text_entries }}</b>
            <span>对话线路</span>
          </div>
          <div>
            <b>{{ provider.vision_entries }}</b>
            <span>图片线路</span>
          </div>
          <div>
            <b>{{ provider.total_entries }}</b>
            <span>全部线路</span>
          </div>
        </div>
        <div class="section-title"><span>识别能力</span></div>
        <div class="capability-grid">
          <div>
            <WebIcon
              aria-hidden="true"
              :type="provider.vision_entries > 0 ? 'settings' : 'circle'"
              size="36"
              :color="
                provider.vision_entries > 0 ? 'var(--color-primary)' : 'var(--color-text-secondary)'
              "
            />
            <b>图片识别</b>
            <span>{{ provider.vision_entries > 0 ? '已配置' : '未配置' }}</span>
          </div>
        </div>
        <div class="section-title"><span>当前智能模型</span></div>
        <div class="card model-card">
          <span class="tag">逻辑模型</span>
          <b>{{ provider.logical_model }}</b>
          <span>文本和图片请求会在 CSU 可用线路之间依次轮询。</span>
          <div class="rotation">
            <span>文本位置 {{ provider.text_cursor ?? 0 }}</span>
            <span>图片位置 {{ provider.vision_cursor ?? 0 }}</span>
            <span>最近状态 {{ statusLabel }}</span>
          </div>
          <button role="button" class="primary-btn" :disabled="probing" @click="probe">
            {{ probing ? '正在检查线路…' : '重新检查智能服务' }}
          </button>
        </div>
        <div v-if="canConfigure" class="section-title"><span>App 本地联调地址</span></div>
        <div v-if="canConfigure" class="card">
          <span class="muted">仅开发包可修改。手机通过网关访问仓颉服务；H5 使用开发代理。</span>
          <div class="field">
            <WebInput
              v-model="apiBase"
              class="field-input"
              placeholder="http://192.168.1.10:8002/api/v1"
            />
          </div>
          <button role="button" class="secondary-btn" @click="saveApi">保存 App 地址</button>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { browser } from '@/platform/browser.js'
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
  browser.getStorageSync('minddimension_api_base') ||
    import.meta.env.VITE_API_BASE_URL ||
    'http://10.0.2.2:8002/api/v1',
)
async function load() {
  error.value = false
  try {
    await store.loadUser()
    if (store.role !== 'admin') {
      browser.reLaunch({ url: roleHome(store.role) })
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
    browser.showToast({ title: '地址已保存', icon: 'success' })
  } catch (err) {
    browser.showToast({ title: err.message, icon: 'none' })
  }
}
onMounted(load)
</script>

<style scoped lang="scss">
.system-status {
  display: flex;
  align-items: center;
  gap: 10.0px;
  padding: 15.0px;
  border-radius: 12.0px;
  background: var(--color-surface);
  color: var(--color-text-primary);
}
.system-status.warn {
  background: var(--color-surface);
}
.system-status span,
.system-status b {
  display: block;
}
.system-status span {
  font-size: 11.0px;
  opacity: 0.7;
}
.system-status b {
  font-size: 17.0px;
  margin-top: 2.0px;
}
.pulse {
  width: 15.0px;
  height: 15.0px;
  border-radius: 50%;
  background: var(--color-primary);
}
.system-status.warn .pulse {
  background: var(--color-error);
}
.system-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 7.5px;
  margin-top: 10.0px;
}
.system-grid div {
  text-align: center;
  padding: 12.5px 4.0px;
  background: #fff;
  border-radius: 10.0px;
}
.system-grid b,
.system-grid span {
  display: block;
}
.system-grid b {
  font-size: 19.0px;
}
.system-grid span {
  font-size: 10.5px;
  color: #94a3b8;
}
.capability-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 6.0px;
}
.capability-grid div {
  text-align: center;
  padding: 11.0px 4.0px;
  background: #fff;
  border-radius: 9.0px;
}
.capability-grid b,
.capability-grid span {
  display: block;
}
.capability-grid b {
  font-size: 11.5px;
  margin-top: 4.0px;
}
.capability-grid span {
  font-size: 9.0px;
  color: #94a3b8;
  margin-top: 2.0px;
}
.model-card > b,
.model-card > span {
  display: block;
}
.model-card > b {
  font-size: 17.0px;
  margin-top: 9.0px;
  color: #0f172a;
}
.model-card > span:nth-child(3) {
  color: #64748b;
  font-size: 11.5px;
  margin-top: 4.0px;
}
.rotation {
  display: flex;
  gap: 5.0px;
  flex-wrap: wrap;
  margin-top: 10.0px;
}
.rotation span {
  padding: 4.5px 7.5px;
  background: #f1f5f9;
  border-radius: 5.0px;
  color: #64748b;
  font-size: 10.0px;
}
</style>
