import { onMounted, onBeforeUnmount } from 'vue'
import { parsePage } from './browser.js'
export function onLoad(callback) { onMounted(() => callback(parsePage(window.location.hash.slice(1)).options)) }
export function onShow(callback) {
  onMounted(callback)
  const visible = () => { if (document.visibilityState === 'visible') callback() }
  document.addEventListener('visibilitychange', visible)
  onBeforeUnmount(() => document.removeEventListener('visibilitychange', visible))
}
export function onHide(callback) {
  const hidden = () => { if (document.visibilityState === 'hidden') callback() }
  document.addEventListener('visibilitychange', hidden)
  onBeforeUnmount(() => { document.removeEventListener('visibilitychange', hidden); callback() })
}
export function onUnload(callback) { onBeforeUnmount(callback) }
