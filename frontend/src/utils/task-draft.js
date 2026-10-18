const prefix = 'minddimension_task_'
const used = new Set()
export function taskRequestId() {
  return (
    globalThis.crypto?.randomUUID?.() ||
    `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`
  )
}
function key(user, task) {
  return `${prefix}${encodeURIComponent(user)}_${encodeURIComponent(task)}`
}
// Raw local state: callers must check the source version before reusing it.
export function readStoredTaskDraft(user, task) {
  let value
  try {
    value = uni.getStorageSync(key(user, task))
  } catch {
    value = null
  }
  return value && typeof value === 'object' && !Array.isArray(value) ? value : null
}
export function readTaskDraft(user, task, fingerprint) {
  const value = readStoredTaskDraft(user, task)
  return value && value.fingerprint === fingerprint
    ? value
    : { fingerprint, text: '', pending: null }
}
export function saveTaskDraft(user, task, value) {
  if (!user || !task) return
  const name = key(user, task)
  used.add(name)
  // Keep Vue proxies out of native bridges and storage adapters.
  try {
    uni.setStorageSync(name, JSON.parse(JSON.stringify(value)))
    return true
  } catch {
    return false
  }
}
export function clearTaskDrafts() {
  const keys = new Set([...used, ...(uni.getStorageInfoSync?.()?.keys || [])])
  for (const name of keys) if (name.startsWith(prefix)) uni.removeStorageSync(name)
  used.clear()
}
export const taskStatusLabel = (status) =>
  ({
    queued: '正在准备',
    running: '正在核对',
    waiting_student: '等你完成这一步',
    needs_review: '还需要核对',
    failed: '可以稍后继续',
    completed: '本次已完成',
    cancelled: '已结束',
    stale: '原题已更新',
  })[status] || '读取中'

// A receipt may advance the cursor locally. An unrelated step must not inherit
// an old answer, pending POST or confirmed photo just because the task is equal.
export function reconcileTaskDraft(value, task) {
  const draft = { ...value }
  const pending = draft.pending
  const own = !!pending && task.last_request_id === pending.request_id
  const changed = draft.step_id !== task.step_id
  if (own) {
    if (!['queued', 'running'].includes(task.status)) {
      if (task.status !== 'failed' && pending.kind === 'answer') draft.text = ''
      draft.pending = null
    }
    draft.step_id = task.step_id
    return { draft, ownTransition: changed, changed: false, fromStep: value.step_id }
  }
  if (changed) {
    const previous =
      draft.text || draft.handwriting_id || draft.pending
        ? {
            text: draft.text || '',
            step_id: draft.step_id || '',
            handwriting_id: draft.handwriting_id || '',
          }
        : draft.previous_draft
    return {
      draft: {
        fingerprint: task.input_fingerprint,
        step_id: task.step_id,
        text: '',
        pending: null,
        previous_draft: previous,
      },
      changed: !!previous,
      ownTransition: false,
      fromStep: value.step_id,
    }
  }
  if (pending && task.version !== pending.version) draft.pending = null
  return { draft, changed: false, ownTransition: false, fromStep: value.step_id }
}

export function advanceTaskDraft(user, task, fromStep, toStep) {
  // Used only after the server acknowledges this client's own request.
  if (!fromStep || !toStep) return
  try {
    const value = uni.getStorageSync(key(user, task))
    if (value && value.step_id === fromStep)
      saveTaskDraft(user, task, { ...value, step_id: toStep })
  } catch {
    /* The task page separately reports unavailable local storage. */
  }
}
