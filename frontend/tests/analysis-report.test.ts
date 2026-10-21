import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import Analysis from '../src/pages/analysis/analysis.vue'
import Teacher from '../src/pages/teacher/student.vue'
const fake = vi.hoisted(() => ({
  getData: vi.fn(),
  go: vi.fn(),
  hooks: {} as Record<string, (...args: any[]) => any>,
}))
vi.mock('@dcloudio/uni-app', () => ({
  onLoad: (fn: any) => (fake.hooks.load = fn),
  onShow: (fn: any) => (fake.hooks.show = fn),
  onHide: (fn: any) => (fake.hooks.hide = fn),
  onUnload: (fn: any) => (fake.hooks.unload = fn),
}))
vi.mock('../src/api/index.js', () => ({ getData: fake.getData }))
vi.mock('../src/utils/navigation.js', () => ({ go: fake.go }))
let wrapper: ReturnType<typeof mount> | undefined
function make() {
  wrapper = mount(Analysis, {
    global: {
      stubs: {
        'app-header': true,
        'state-panel': true,
        'cognition-canvas': true,
        'uni-icons': true,
        'math-text': { props: ['text'], template: '<span>{{text}}</span>' },
      },
    },
  })
  fake.hooks.load({})
  return wrapper
}
beforeEach(() => fake.getData.mockReset())
afterEach(() => wrapper?.unmount())
it('知识图谱未读取时不宣称为空，切换学科等待或失败时不显示旧关系', async () => {
  const page = make()
  fake.hooks.load({ relations: '1' })
  expect(page.find('.relation-summary text').exists()).toBe(false)
  let resolve: (value: any) => void = () => {}
  fake.getData.mockReturnValueOnce(new Promise((done) => (resolve = done)))
  fake.hooks.show()
  await flushPromises()
  expect(page.find('cognition-canvas-stub').exists()).toBe(false)
  expect(page.find('state-panel-stub').attributes('state')).toBe('loading')
  resolve({
    mapped_question_count: 3,
    nodes: [{ id: 'k', category: 'knowledge', name: '等式' }],
    links: [],
  })
  await flushPromises()
  expect(page.find('.relation-summary text').text()).toContain('3 道错题关联到 1 个知识点')
  let reject: (error: Error) => void = () => {}
  fake.getData.mockReturnValueOnce(new Promise((_, fail) => (reject = fail)))
  await page.findAll('.chip')[1].trigger('click')
  expect(page.find('.relation-summary text').exists()).toBe(false)
  expect(page.find('cognition-canvas-stub').exists()).toBe(false)
  reject(new Error('暂时无法加载'))
  await flushPromises()
  expect(page.find('state-panel-stub').attributes('state')).toBe('error')
  expect(page.text()).not.toContain('暂无知识关系')
})
it('返回报告重新读取，离开后迟到结果不能恢复旧数据', async () => {
  let resolve: (value: any) => void = () => {}
  fake.getData.mockReturnValueOnce(
    new Promise((done) => {
      resolve = done
    }),
  )
  const page = make()
  fake.hooks.show()
  fake.hooks.hide()
  resolve({
    mastery: [{ subject: '数学', knowledge_point: '旧数据', mastery_score: 0.2 }],
    misconceptions: [],
    trend: [],
  })
  await flushPromises()
  expect(page.text()).not.toContain('旧数据')
  fake.getData.mockResolvedValueOnce({
    mastery: [{ subject: '物理', knowledge_point: '受力分析', mastery_score: 0.4 }],
    misconceptions: [],
    trend: [],
  })
  await fake.hooks.show()
  await flushPromises()
  expect(page.text()).toContain('物理 · 近期学习')
  expect(page.text()).toContain('受力分析')
  await page.find('.progress-block button').trigger('click')
  const destination = new URL(fake.go.mock.calls.at(-1)![0], 'https://local.test')
  expect(destination.searchParams.get('subject')).toBe('物理')
  expect(destination.searchParams.get('search')).toBe('')
  expect(fake.getData).toHaveBeenCalledTimes(2)
})

it('教师返回学生详情时重新读取，离开后的旧报告不会恢复', async () => {
  let resolve: (value: any) => void = () => {}
  fake.getData.mockReturnValueOnce(
    new Promise((done) => {
      resolve = done
    }),
  )
  wrapper = mount(Teacher, { global: { stubs: { 'app-header': true, 'state-panel': true } } })
  fake.hooks.load({ id: 'student', class_id: 'class' })
  fake.hooks.show()
  fake.hooks.hide()
  resolve({
    student: { name: '旧学生' },
    summary: {},
    mastery: [],
    misconceptions: [],
    recent_updates: [],
  })
  await flushPromises()
  expect(wrapper.find('.teacher-grid').exists()).toBe(false)
  fake.getData.mockResolvedValueOnce({
    student: { id: 'student' },
    summary: { questions: 2 },
    mastery: [
      {
        id: 'm',
        subject: '化学',
        knowledge_point: '化学方程式',
        mastery_score: 0.4,
        evidence_count: 2,
      },
    ],
    misconceptions: [],
    recent_updates: [],
  })
  await fake.hooks.show()
  await flushPromises()
  expect(wrapper.find('.metric-value').text()).toBe('2')
  expect(wrapper.text()).toContain('化学方程式')
  expect(fake.getData).toHaveBeenLastCalledWith('/teachers/students/student/report')
})
