import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import Learning from '../src/pages/learning/learning.vue'
import Notebook from '../src/pages/problem/list.vue'

const mocks = vi.hoisted(() => ({
  getData: vi.fn(),
  go: vi.fn(),
  callbacks: [] as (() => Promise<void>)[],
  store: { user: { id: 'student-ui' }, loadUser: vi.fn() },
}))
vi.mock('@dcloudio/uni-app', () => ({
  onShow: (fn: () => Promise<void>) => mocks.callbacks.push(fn),
  onLoad: vi.fn(),
}))
vi.mock('../src/api/index.js', () => ({ getData: mocks.getData, mediaUrl: (url: string) => url }))
vi.mock('../src/utils/navigation.js', () => ({ go: mocks.go }))
vi.mock('../src/store/index.js', () => ({ useAppStore: () => mocks.store }))
const global = {
  stubs: { 'app-header': true, 'tab-bar': true, 'uni-icons': true, 'state-panel': true },
}
const wrappers: ReturnType<typeof mount>[] = []
const button = (wrapper: ReturnType<typeof mount>, label: string) => {
  const target = wrapper.findAll('button').find((b) => b.text().trim() === label)
  if (!target) throw Error('missing button: ' + label)
  return target
}
beforeEach(() => {
  mocks.callbacks.length = 0
  mocks.getData.mockReset()
  mocks.go.mockReset()
})
afterEach(() => {
  wrappers.splice(0).forEach((w) => w.unmount())
})

describe('学生页面按需展开', () => {
  it('错题列表渲染上传题目的分式、根号和下标，保留完整题干与跳转', async () => {
    const fraction = String.raw`9，若不论 k 为何值，直线 $y=k(x-1)-\frac{k^2}{4}$ 与抛物线 $y=ax^2+bx+c$ 有且只有一个公共点，求 a、b、c 的值。`
    const geometry = String.raw`7. 如图，直线 $y=\sqrt{3}x$，点 $A_1$ 坐标为 $(1,0)$，过点 $A_1$ 作 $x$ 轴的垂线交直线于点 $B_1$；以原点 $O$ 为圆心，$OB_1$ 长为半径画弧交 $x$ 轴于点 $A_2$。这是完整题干的末尾。`
    mocks.getData.mockResolvedValue([
      { id: 'q-fraction', subject: '数学', question_text: fraction },
      { id: 'q-geometry', subject: '数学', question_text: geometry },
      { id: 'q-pending', subject: '语文', question_text: '' },
    ])
    const wrapper = mount(Notebook, { global })
    wrappers.push(wrapper)
    await mocks.callbacks[0]()
    await flushPromises()
    const cards = wrapper.findAll('.problem-card')
    expect(cards[0].findAll('.katex')).toHaveLength(2)
    expect(cards[0].find('.mfrac').exists()).toBe(true)
    expect(cards[1].find('.sqrt').exists()).toBe(true)
    expect(cards[1].find('.msupsub').exists()).toBe(true)
    expect(cards[1].text()).toContain('这是完整题干的末尾。')
    expect(wrapper.find('.katex-display').exists()).toBe(false)
    expect(wrapper.find('.math-unparsed').exists()).toBe(false)
    expect(cards[2].text()).toContain('题目正在整理中')
    await cards[0].trigger('click')
    expect(mocks.go.mock.calls.at(-1)![0]).toContain('q-fraction')
  })

  it('学习中心先显示四种方式，记录展开后仍能进入原页面', async () => {
    const wrapper = mount(Learning, { global })
    wrappers.push(wrapper)
    expect(wrapper.findAll('.feature-link')).toHaveLength(4)
    expect(wrapper.text()).not.toContain('复习记录')
    await button(wrapper, '更多记录与任务').trigger('click')
    await button(wrapper, '复习记录').trigger('click')
    expect(mocks.go).toHaveBeenCalledWith('/pages/review/review?history=1')
    await button(wrapper, '更多记录与任务').trigger('click')
    expect(wrapper.text()).not.toContain('复习记录')
    await wrapper.findAll('.feature-link')[2].trigger('keydown', { key: 'Enter' })
    expect(mocks.go).toHaveBeenCalledWith('/pages/paper/paper-center')
  })
  it('取消筛选不会改变题目，应用收藏后组卷只携带实际可见ID', async () => {
    mocks.getData.mockResolvedValue([
      { id: 'q1', subject: '数学', grade: '初一', question_text: '题目甲', favorite: true },
      { id: 'q2', subject: '数学', grade: '初一', question_text: '题目乙', favorite: false },
    ])
    const wrapper = mount(Notebook, { global })
    wrappers.push(wrapper)
    await mocks.callbacks[0]()
    await flushPromises()
    expect(wrapper.findAll('.problem-card')).toHaveLength(2)
    expect(wrapper.find('.filter-sheet').exists()).toBe(false)
    await button(wrapper, '筛选').trigger('click')
    await button(wrapper, '仅收藏').trigger('click')
    await button(wrapper, '取消').trigger('click')
    expect(wrapper.findAll('.problem-card')).toHaveLength(2)
    await button(wrapper, '筛选').trigger('click')
    expect(button(wrapper, '仅收藏').attributes('aria-pressed')).toBe('false')
    await button(wrapper, '仅收藏').trigger('click')
    await button(wrapper, '应用筛选').trigger('click')
    expect(wrapper.findAll('.problem-card')).toHaveLength(1)
    expect(wrapper.find('.problem-card').text()).toContain('题目甲')
    await button(wrapper, '按当前条件组卷').trigger('click')
    const destination = new URL(mocks.go.mock.calls.at(-1)![0], 'https://local.test')
    expect(destination.searchParams.get('ids')).toBe('q1')
  })
})
