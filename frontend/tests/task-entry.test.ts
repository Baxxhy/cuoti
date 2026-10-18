import { beforeEach, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'

const api = vi.hoisted(() => ({ getData: vi.fn(), postData: vi.fn() }))
vi.mock('../src/api/index.js', () => api)
import { requestLearningTask } from '../src/utils/task-entry.js'

let storage: Map<string, any>
beforeEach(() => {
  storage = new Map([['minddimension_access_token', 'token-a']])
  api.getData.mockReset().mockResolvedValue({ id: 'user-a' })
  api.postData.mockReset()
  vi.stubGlobal('uni', {
    getStorageSync: (key: string) => storage.get(key),
    setStorageSync: (key: string, value: any) => storage.set(key, value),
    removeStorageSync: (key: string) => storage.delete(key),
  })
})

it('两个入口同时进入同题共用一次创建，得到同一服务端回执', async () => {
  let finish: (value: any) => void = () => {}
  api.postData.mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve
      }),
  )
  const first = requestLearningTask('q-1'),
    second = requestLearningTask('q-1')
  await flushPromises()
  expect(api.postData).toHaveBeenCalledTimes(1)
  expect(api.postData.mock.calls[0][0]).toBe('/learning-tasks')
  finish({ id: 'task-1' })
  expect(await Promise.all([first, second])).toEqual([{ id: 'task-1' }, { id: 'task-1' }])
  expect(storage.has('minddimension_task_create_user-a_q-1')).toBe(false)
})

it('丢失回执后重试复用原编号，成功才清除', async () => {
  api.postData.mockRejectedValueOnce(new Error('连接中断'))
  await expect(requestLearningTask('q-2')).rejects.toThrow('连接中断')
  const pending = storage.get('minddimension_task_create_user-a_q-2')
  expect(pending).toBeTruthy()
  api.postData.mockResolvedValue({ id: 'task-2' })
  await requestLearningTask('q-2')
  expect(api.postData.mock.calls.map((call) => call[1].request_id)).toEqual([pending, pending])
  expect(storage.has('minddimension_task_create_user-a_q-2')).toBe(false)
})

it('账号变化时不交付旧回执，不清除旧用户的请求编号', async () => {
  let finish: (value: any) => void = () => {}
  api.postData.mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve
      }),
  )
  const pending = requestLearningTask('q-3')
  await flushPromises()
  storage.set('minddimension_access_token', 'token-b')
  finish({ id: 'old-task' })
  await expect(pending).rejects.toThrow('账号已变化')
  const oldRequest = storage.get('minddimension_task_create_user-a_q-3')
  api.getData.mockResolvedValue({ id: 'user-b' })
  api.postData.mockResolvedValue({ id: 'new-task' })
  await expect(requestLearningTask('q-3')).resolves.toEqual({ id: 'new-task' })
  expect(api.postData.mock.calls[1][1].request_id).not.toBe(oldRequest)
})

it('身份查询期间换账号则不创建任何任务', async () => {
  let finish: (value: any) => void = () => {}
  api.getData.mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve
      }),
  )
  const pending = requestLearningTask('q-4')
  storage.set('minddimension_access_token', 'token-b')
  finish({ id: 'old-user' })
  await expect(pending).rejects.toThrow('账号已变化')
  expect(api.postData).not.toHaveBeenCalled()
})
