import { expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import Bank from '../src/pages/bank/bank.vue'
const fake = vi.hoisted(() => ({ getData: vi.fn(), show: () => {}, load: (_: any) => {} }))
vi.mock('@dcloudio/uni-app', () => ({
  onLoad: (fn: any) => (fake.load = fn),
  onShow: (fn: any) => (fake.show = fn),
}))
vi.mock('../src/api/index.js', () => ({
  getData: fake.getData,
  postData: vi.fn(),
  mediaUrl: (x: string) => x,
}))
vi.mock('../src/utils/navigation.js', () => ({ go: vi.fn() }))
it('历史请求未完成时题目仍可显示，切换学科不重复读取历史，页面不展示总题数', async () => {
  fake.getData.mockImplementation((url: string) =>
    url === '/study-sessions'
      ? new Promise(() => {})
      : Promise.resolve({
          total: 124394,
          facets: [{ subject: '数学', grade_band: '初中' }],
          questions: [
            {
              id: 'q1',
              subject: '数学',
              grade_band: '初中',
              question_type: '计算题',
              question_text: '求 1+1',
            },
          ],
        }),
  )
  const page = mount(Bank, {
    global: {
      stubs: {
        'app-header': true,
        'tab-bar': true,
        'state-panel': true,
        'math-text': { props: ['text'], template: '<span>{{ text }}</span>' },
      },
    },
  })
  fake.load({})
  fake.show()
  await flushPromises()
  expect(page.find('.bank-question').text()).toContain('求 1+1')
  expect(page.text()).not.toContain('124394')
  await page.findAll('.bank-subjects button')[1].trigger('click')
  await flushPromises()
  expect(fake.getData.mock.calls.filter(([url]) => url === '/study-sessions')).toHaveLength(1)
  expect(fake.getData.mock.calls.some(([url]) => url.includes('subject=%E6%95%B0%E5%AD%A6'))).toBe(
    true,
  )
  page.unmount()
})
