import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  clearTaskDrafts,
  readTaskDraft,
  saveTaskDraft,
  reconcileTaskDraft,
} from '../src/utils/task-draft.js'
let storage: Map<string, any>
beforeEach(() => {
  storage = new Map()
  vi.stubGlobal('uni', {
    getStorageSync: (key: string) => storage.get(key),
    setStorageSync: (key: string, value: unknown) => storage.set(key, value),
    removeStorageSync: (key: string) => storage.delete(key),
    getStorageInfoSync: () => ({ keys: [...storage.keys()] }),
  })
})
afterEach(() => vi.unstubAllGlobals())
describe('学习任务草稿边界', () => {
  it('按用户、任务和题目版本隔离；退出清理草稿但不删除其他偏好', () => {
    saveTaskDraft('a', 't1', { fingerprint: 'f1', text: '2x=8', pending: { request_id: 'stable' } })
    expect(readTaskDraft('a', 't1', 'f1').text).toBe('2x=8')
    expect(readTaskDraft('b', 't1', 'f1').text).toBe('')
    expect(readTaskDraft('a', 't2', 'f1').text).toBe('')
    expect(readTaskDraft('a', 't1', 'f2').text).toBe('')
    storage.set('unrelated', 'keep')
    clearTaskDrafts()
    expect(readTaskDraft('a', 't1', 'f1').text).toBe('')
    expect(storage.get('unrelated')).toBe('keep')
  })
})

it('旧照片和请求不随远端新步骤带入；已确认的本机辅助动作可保留作答', () => {
  const old = {
    fingerprint: 'fp',
    step_id: 's1',
    text: '旧文字',
    handwriting_id: 'old-photo',
    pending: { request_id: 'old-post', kind: 'answer', version: 1 },
  }
  const remote = reconcileTaskDraft(old, {
    input_fingerprint: 'fp',
    step_id: 's2',
    version: 4,
    status: 'waiting_student',
    last_request_id: 'remote',
  })
  expect(remote.draft.text).toBe('')
  expect(remote.draft.handwriting_id).toBeUndefined()
  expect(remote.draft.pending).toBeNull()
  expect(remote.draft.previous_draft.text).toBe('旧文字')
  const own = reconcileTaskDraft(
    { ...old, pending: { ...old.pending, kind: 'hint' } },
    { step_id: 's2', version: 4, status: 'waiting_student', last_request_id: 'old-post' },
  )
  expect(own.ownTransition).toBe(true)
  expect(own.draft.text).toBe('旧文字')
  expect(own.draft.handwriting_id).toBe('old-photo')
})
