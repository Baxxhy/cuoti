import { afterEach, describe, expect, it, vi } from 'vitest'
import { back, returnToQuestion } from '../src/utils/navigation.js'

afterEach(() => vi.unstubAllGlobals())

describe('返回导航', () => {
  it.each([
    ['pages/teacher/classes', '/pages/teacher/dashboard'],
    ['pages/guardian/report', '/pages/guardian/home'],
    ['pages/system/system', '/pages/admin/workbench'],
    ['pages/forgot/forgot', '/pages/login/login'],
    ['pages/detail/detail', '/pages/index/index'],
  ])('直接打开 %s 后返回对应入口', (route, expected) => {
    const reLaunch = vi.fn()
    vi.stubGlobal('uni', { reLaunch, navigateBack: vi.fn() })
    vi.stubGlobal('getCurrentPages', () => [{ route }])
    back()
    expect(reLaunch).toHaveBeenCalledWith({ url: expected })
  })

  it('有历史页面时返回上一页，而不是切换角色入口', () => {
    const navigateBack = vi.fn(),
      reLaunch = vi.fn()
    vi.stubGlobal('uni', { reLaunch, navigateBack })
    vi.stubGlobal('getCurrentPages', () => [
      { route: 'pages/teacher/classes' },
      { route: 'pages/teacher/student' },
    ])
    back()
    expect(navigateBack).toHaveBeenCalledOnce()
    expect(reLaunch).not.toHaveBeenCalled()
  })
})

describe('任务返回原题', () => {
  it('复用同一道题的已有页面，避免每轮学习增加一层', () => {
    const navigateBack = vi.fn(),
      reLaunch = vi.fn()
    vi.stubGlobal('uni', { navigateBack, reLaunch })
    vi.stubGlobal('getCurrentPages', () => [
      { route: 'pages/problem/list' },
      { route: 'pages/detail/detail', $page: { fullPath: '/pages/detail/detail?id=q1' } },
      { route: 'pages/task/task' },
    ])
    returnToQuestion('q1')
    expect(navigateBack).toHaveBeenCalledWith({ delta: 1 })
    expect(reLaunch).not.toHaveBeenCalled()
  })
  it('历史中的其他题目不会被当作当前原题', () => {
    const navigateBack = vi.fn(),
      reLaunch = vi.fn()
    vi.stubGlobal('uni', { navigateBack, reLaunch })
    vi.stubGlobal('getCurrentPages', () => [
      { route: 'pages/detail/detail', options: { id: 'q2' } },
      { route: 'pages/task/task' },
    ])
    returnToQuestion('q1')
    expect(reLaunch).toHaveBeenCalledWith({ url: '/pages/detail/detail?id=q1' })
    expect(navigateBack).not.toHaveBeenCalled()
  })
})
