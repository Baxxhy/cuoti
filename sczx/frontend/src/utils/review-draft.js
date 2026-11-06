import {
  readTaskDraft,
  readStoredTaskDraft,
  saveTaskDraft,
  taskRequestId,
} from '@/utils/task-draft.js'

const draftId = (plan) => `review:${plan.id}`
export function readReviewDraft(user, plan) {
  return reconcileReviewDraft(readStoredTaskDraft(user, draftId(plan)), plan)
}
// Preserve stale text for review, never its pending submission or photo.
export function reconcileReviewDraft(value, plan) {
  const fingerprint = plan.source_version || ''
  const current = value?.fingerprint === fingerprint
  const candidate = current
    ? value.previous_draft
    : typeof value?.text === 'string' && value.text.trim()
      ? value
      : value?.previous_draft
  const previous =
    candidate &&
    typeof candidate.fingerprint === 'string' &&
    candidate.fingerprint !== fingerprint &&
    typeof candidate.text === 'string' &&
    candidate.text.trim() &&
    candidate.text.length <= 12000
      ? { fingerprint: candidate.fingerprint, text: candidate.text }
      : null
  return current
    ? { ...value, previous_draft: previous }
    : { fingerprint, text: '', pending: null, previous_draft: previous }
}

export function saveReviewDraft(
  user,
  plan,
  text,
  pending = null,
  image = '',
  recognition = null,
  dismissed = '',
  previous = null,
) {
  return saveTaskDraft(user, draftId(plan), {
    fingerprint: plan.source_version || '',
    text: text || '',
    pending,
    image,
    recognition,
    dismissed_attempt: dismissed,
    previous_draft: previous,
  })
}
export function reviewSubmission(plan, text, image, recognition, previous) {
  const payload = {
    answer: text,
    handwriting_image_url: image || '',
    handwriting_recognition: recognition || null,
    source_version: plan.source_version || '',
  }
  if (previous && JSON.stringify(previous.payload) === JSON.stringify(payload)) return previous
  return { request_id: taskRequestId(), payload }
}

export function readReviewPosition(user) {
  return readTaskDraft(user, 'review-queue', 'queue').text || ''
}
export function saveReviewPosition(user, planId) {
  return saveTaskDraft(user, 'review-queue', { fingerprint: 'queue', text: planId })
}

export function readReviewText(user, planId, cached = null) {
  const value = cached || readStoredTaskDraft(user, draftId({ id: planId }))
  const text =
    typeof value?.text === 'string' && value.text.trim() ? value.text : value?.previous_draft?.text
  return typeof text === 'string' && text.length <= 12000 ? text : ''
}
