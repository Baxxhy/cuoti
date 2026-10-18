import { beforeEach, describe, expect, it, vi } from 'vitest'
import { postData, request, uploadFile } from '../src/api/index.js'

describe('API 请求超时', () => {
  const send = vi.fn((options) =>
    options.success({
      statusCode: 200,
      data: { data: { question_id: 'practice-question' } },
    }),
  )

  beforeEach(() => {
    send.mockClear()
    vi.stubGlobal('uni', {
      getStorageSync: vi.fn(() => ''),
      request: send,
    })
  })

  it('postData 将较长的匹配超时传给 uni.request', async () => {
    const body = { mistake_id: 'mistake-1', mode: 'reinforce' }

    await expect(postData('/practice/recommend', body, { timeout: 300000 })).resolves.toEqual({
      question_id: 'practice-question',
    })

    expect(send).toHaveBeenCalledWith(
      expect.objectContaining({
        url: '/api/v1/practice/recommend',
        method: 'POST',
        data: body,
        timeout: 300000,
      }),
    )
  })

  it('postData 未指定超时时仍等待 60 秒', async () => {
    await postData('/practice/attempt', { student_answer: 'A' })

    expect(send).toHaveBeenCalledWith(expect.objectContaining({ timeout: 60000 }))
  })
})

describe('API 未授权处理', () => {
  const removeStorageSync = vi.fn()
  const reLaunch = vi.fn()

  beforeEach(() => {
    removeStorageSync.mockReset()
    reLaunch.mockReset()
    vi.stubGlobal('uni', {
      getStorageSync: vi.fn(() => 'expired-token'),
      removeStorageSync,
      reLaunch,
      showToast: vi.fn(),
      request: vi.fn((options) =>
        options.success({
          statusCode: 401,
          data: { detail: '登录已失效' },
        }),
      ),
      uploadFile: vi.fn((options) =>
        options.success({
          statusCode: 401,
          data: JSON.stringify({ detail: '登录已失效' }),
        }),
      ),
    })
  })

  it('受保护请求返回 401 时清除 Token 并跳转登录页', async () => {
    await expect(request('/dashboard', { silent: true })).rejects.toThrow('登录已失效')

    expect(removeStorageSync).toHaveBeenCalledWith('minddimension_access_token')
    expect(reLaunch).toHaveBeenCalledWith({ url: '/pages/login/login' })
  })

  it('在请求错误上保留 HTTP 状态码', async () => {
    try {
      await request('/dashboard', { silent: true })
      throw new Error('request should reject')
    } catch (error) {
      expect(error).toMatchObject({ statusCode: 401 })
    }
  })

  it('静默恢复会话时只清除失效 Token，不重复跳转', async () => {
    await expect(
      request('/auth/me', {
        silent: true,
        skipAuthRedirect: true,
      }),
    ).rejects.toThrow('登录已失效')

    expect(removeStorageSync).toHaveBeenCalledWith('minddimension_access_token')
    expect(reLaunch).not.toHaveBeenCalled()
  })

  it('上传请求返回 401 时同样回到登录页', async () => {
    await expect(uploadFile('/questions', 'question.jpg')).rejects.toThrow('登录已失效')

    expect(removeStorageSync).toHaveBeenCalledWith('minddimension_access_token')
    expect(reLaunch).toHaveBeenCalledWith({ url: '/pages/login/login' })
  })
})
