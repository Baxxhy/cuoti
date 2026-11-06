import { getData, postData } from '@/api/index.js'
import { taskRequestId } from '@/utils/task-draft.js'

const inFlight = new Map()
const tokenKey = 'minddimension_access_token'

// Share the receipt across entry pages and transport retries. The server still
// decides task ownership, current source version and whether an active task exists.
export async function requestLearningTask(questionId) {
  const token = uni.getStorageSync(tokenKey)
  const user = await getData('/auth/me', { silent: true })
  if (uni.getStorageSync(tokenKey) !== token || !user?.id)
    throw new Error('账号已变化，请重新进入这道题。')
  const key = `minddimension_task_create_${user.id}_${questionId}`
  const previous = inFlight.get(key)
  if (previous?.token === token) return previous.promise
  const stored = uni.getStorageSync(key)
  const requestId =
    typeof stored === 'string' && stored.length > 0 && stored.length <= 80
      ? stored
      : taskRequestId()
  uni.setStorageSync(key, requestId)
  const promise = Promise.resolve().then(async () => {
    try {
      const task = await postData('/learning-tasks', {
        question_id: questionId,
        request_id: requestId,
      })
      if (uni.getStorageSync(tokenKey) !== token) throw new Error('账号已变化，请重新进入这道题。')
      if (!task?.id) throw new Error('未能读取学习记录，请重试。')
      uni.removeStorageSync(key)
      return task
    } finally {
      if (inFlight.get(key)?.promise === promise) inFlight.delete(key)
    }
  })
  inFlight.set(key, { token, promise })
  return promise
}
