import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const apiMocks = vi.hoisted(() => ({
  getData: vi.fn(),
  postData: vi.fn(),
}))

vi.mock('../src/api/index.js', () => apiMocks)

import { useAppStore } from '../src/store/index.js'

describe('登录会话恢复', () => {
  let storage: Map<string, string>

  beforeEach(() => {
    setActivePinia(createPinia())
    storage = new Map()
    apiMocks.getData.mockReset()
    apiMocks.postData.mockReset()
    vi.stubGlobal('uni', {
      getStorageSync: vi.fn((key: string) => storage.get(key) || ''),
      setStorageSync: vi.fn((key: string, value: string) => storage.set(key, value)),
      removeStorageSync: vi.fn((key: string) => storage.delete(key)),
      reLaunch: vi.fn(),
    })
  })

  it('没有本地 Token 时停留在登录页', async () => {
    const store = useAppStore()

    await expect(store.restoreSession()).resolves.toBeNull()
    expect(apiMocks.getData).not.toHaveBeenCalled()
  })

  it('使用本地 Token 恢复用户和角色', async () => {
    storage.set('minddimension_access_token', 'saved-token')
    const user = { id: 'student-id', name: 'chs', role: 'student' }
    apiMocks.getData.mockResolvedValue(user)
    const store = useAppStore()

    await expect(store.restoreSession()).resolves.toEqual(user)
    expect(apiMocks.getData).toHaveBeenCalledWith('/auth/me', {
      silent: true,
      skipAuthRedirect: true,
    })
    expect(store.user).toEqual(user)
    expect(store.role).toBe('student')
  })

  it('恢复失败时清空内存用户状态', async () => {
    storage.set('minddimension_access_token', 'expired-token')
    apiMocks.getData.mockRejectedValue(new Error('expired'))
    const store = useAppStore()
    store.user = { id: 'stale-user' }
    store.role = 'teacher'

    await expect(store.restoreSession()).resolves.toBeNull()
    expect(store.user).toBeNull()
    expect(store.role).toBe('student')
  })
})
