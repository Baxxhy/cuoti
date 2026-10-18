import { mount, flushPromises } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
const hooks = vi.hoisted(() => ({ load: null as any }))
vi.mock('@dcloudio/uni-app', () => ({
  onLoad: (fn: any) => {
    hooks.load = fn
  },
}))
vi.mock('../src/api/index.js', () => ({ getData: vi.fn() }))
import { getData } from '../src/api/index.js'
import Library from '../src/pages/library/library.vue'
const setup = () =>
  mount(Library, {
    global: {
      stubs: {
        'app-header': true,
        'math-text': { props: ['text'], template: '<span>{{ text }}</span>' },
        'state-panel': { props: ['message'], template: '<div>{{ message }}</div>' },
      },
    },
  })
afterEach(() => {
  vi.resetAllMocks()
  vi.unstubAllGlobals()
})
describe('知识库真实请求与返回', () => {
  it('搜索结果进入知识详情，相关错题携带学科和知识名称', async () => {
    const navigateTo = vi.fn()
    vi.stubGlobal('uni', { navigateTo })
    vi.mocked(getData).mockResolvedValue({
      code: 'math-1',
      name: '方程',
      subject: '数学',
      content: { definition: '含未知数的等式', formulas: ['x+1=2'] },
      prerequisites: [],
      next_knowledge: [],
    })
    const wrapper = setup()
    hooks.load({ code: 'math-1' })
    await flushPromises()
    expect(getData).toHaveBeenCalledWith('/knowledge/cards/math-1')
    expect(wrapper.text()).toContain('含未知数的等式')
    await wrapper
      .findAll('button')
      .find((b) => b.text() === '查看相关错题')!
      .trigger('click')
    const url = new URL(navigateTo.mock.calls[0][0].url, 'https://local.test')
    expect(url.searchParams.get('search')).toBe('方程')
    expect(url.searchParams.get('subject')).toBe('数学')
    wrapper.unmount()
  })
  it('空态可清除条件，不制造示例卡片', async () => {
    vi.mocked(getData).mockResolvedValue([])
    const wrapper = setup()
    hooks.load({ q: '不存在的概念', subject: '数学' })
    await flushPromises()
    expect(wrapper.text()).toContain('没有找到符合条件的知识卡')
    await wrapper
      .findAll('button')
      .find((b) => b.text() === '清除条件')!
      .trigger('click')
    await flushPromises()
    expect(getData).toHaveBeenLastCalledWith('/knowledge/cards?q=&subject=&grade=')
    wrapper.unmount()
  })
})
