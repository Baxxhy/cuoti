const pendingStatuses = new Set([
  'awaiting_crop',
  'needs_confirmation',
  'ocr_draft',
  'processing',
  'pending',
  'partial',
])
export function needsConfirmation(item) {
  return item.confirmed === false || pendingStatuses.has(item.status)
}
export function hasDiagnosis(item) {
  return !!item.diagnosis_summary && item.diagnosis_summary !== '等待完成错因诊断'
}
export function studyDate(value) {
  if (!value) return '日期未记录'
  const timestamp = new Date(value).getTime()
  if (!Number.isFinite(timestamp)) return '日期待核对'
  // Match the UTC+8 learning/review calendar, independent of device timezone.
  return new Date(timestamp + 8 * 3600000).toISOString().slice(0, 10)
}
export function dueToday(value, now = new Date()) {
  if (!value) return false
  const time = new Date(value).getTime()
  // Review scheduling uses China local days, independent of device timezone.
  const day = 86400000,
    offset = 8 * 3600000
  return (
    Number.isFinite(time) && time < (Math.floor((now.getTime() + offset) / day) + 1) * day - offset
  )
}
/** @template T
 * @param {T[]} items
 * @param {Object} filters
 * @param {Date} now
 * @returns {T[]}
 */
export function filterQuestions(items, filters = {}, now = new Date()) {
  return items.filter((item) => {
    if (filters.subject && item.subject !== filters.subject) return false
    if (filters.favorite && !item.favorite) return false
    if (filters.due && !dueToday(item.review_due_at, now)) return false
    if (filters.stage === 'confirm' && !needsConfirmation(item)) return false
    if (filters.stage === 'diagnose' && (needsConfirmation(item) || hasDiagnosis(item)))
      return false
    if (filters.stage === 'learn' && (needsConfirmation(item) || !hasDiagnosis(item))) return false
    return true
  })
}
export function questionStatus(item) {
  if (needsConfirmation(item)) return '待核对'
  if (!hasDiagnosis(item)) return '待找错因'
  return item.review_due_at ? '待复习' : '继续学习'
}
export function groupQuestions(items, mode = 'none') {
  if (mode === 'none') return [{ key: 'all', title: '', items }]
  const groups = new Map()
  for (const item of items) {
    const label =
      mode === 'cause'
        ? hasDiagnosis(item)
          ? item.diagnosis_summary
          : '尚无错因'
        : item.knowledge_points?.[0] || '尚无知识点'
    // Never merge the same label across subjects or grades.
    const key = JSON.stringify([item.subject, item.grade, label])
    if (!groups.has(key))
      groups.set(key, { key, title: label, subject: item.subject, grade: item.grade, items: [] })
    groups.get(key).items.push(item)
  }
  return [...groups.values()]
}
export function questionSearchURL(filters = {}) {
  const values = [
    ['subject', filters.subject],
    ['search', filters.search],
  ]
  const query = values
    .filter(([, value]) => value)
    .map(([key, value]) => `${key}=${encodeURIComponent(value)}`)
    .join('&')
  return `/questions${query ? `?${query}` : ''}`
}
export function scopedQuestionURL({ subject = '', search = '' } = {}) {
  return `/pages/problem/list?subject=${encodeURIComponent(subject)}&search=${encodeURIComponent(search)}`
}
/** @param {{subject?: string, knowledge?: string, ids?: string[]}} options */
export function paperURL({ subject = '', knowledge = '', ids = [] } = {}) {
  return `/pages/paper/paper-center?subject=${encodeURIComponent(subject)}&knowledge=${encodeURIComponent(knowledge)}${ids.length ? `&ids=${encodeURIComponent(ids.join(','))}` : ''}`
}
// Only presentation preferences; never cache learning evidence or answers here.
const notebookViews = new Map()
export function saveNotebookView(userId, view) {
  if (userId) notebookViews.set(userId, { ...view })
}
export function notebookView(userId) {
  return { ...(notebookViews.get(userId) || {}) }
}
export function clearNotebookViews() {
  notebookViews.clear()
}
