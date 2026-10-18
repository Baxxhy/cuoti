import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import Assignment from '../src/pages/assignment/assignment.vue'
const fake = vi.hoisted(() => ({ getData: vi.fn(), postData: vi.fn(), show: () => {} }))
vi.mock('@dcloudio/uni-app', () => ({ onShow: (fn: any) => (fake.show = fn) }))
vi.mock('../src/api/index.js', () => ({ getData: fake.getData, postData: fake.postData }))
let wrapper: ReturnType<typeof mount> | undefined
const row = (id: string, status = 'pending') => ({
  student_assignment: { id, status },
  assignment: { title: `作业${id}`, settings: {} },
  question: { subject: '数学', question_type: '计算题', question_text: `题目${id}`, options: [] },
})
async function make(rows: any[]) {
  fake.getData.mockResolvedValue(rows)
  wrapper = mount(Assignment, {
    global: {
      stubs: {
        'app-header': true,
        'state-panel': true,
        'math-text': { props: ['text'], template: '<span>{{text}}</span>' },
        'written-answer': {
          name: 'WrittenAnswer',
          props: ['modelValue'],
          template:
            '<textarea :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
        },
      },
    },
  })
  fake.show()
  await flushPromises()
  return wrapper
}
beforeEach(() => {
  fake.getData.mockReset()
  fake.postData.mockReset()
  vi.stubGlobal('uni', { showToast: vi.fn() })
})
afterEach(() => {
  wrapper?.unmount()
  vi.unstubAllGlobals()
})
it('shows one pending assignment at a time and keeps text when switching', async () => {
  const page = await make([row('old', 'completed'), row('one'), row('two')])
  const bodies = page.findAll('.assignment-body')
  // jsdom caches getComputedStyle for custom uni view elements; check the actual
  // DOM display state here and exercise browser visibility in Playwright.
  const visible = () =>
    page
      .findAll('.assignment-body')
      .map((item) => (item.element as HTMLElement).style.display !== 'none')
  expect(visible()).toEqual([false, true, false])
  await bodies[1].find('textarea').setValue('我的第一项作答')
  await page.findAll('.assignment-header')[2].trigger('click')
  await flushPromises()
  expect(visible()).toEqual([false, false, true])
  await page.findAll('.assignment-header')[1].trigger('click')
  expect((bodies[1].find('textarea').element as HTMLTextAreaElement).value).toBe('我的第一项作答')
  expect(page.findAll('.assignment-header')[1].attributes('aria-expanded')).toBe('true')
})
it('failed submission keeps the answer and permits retry', async () => {
  const page = await make([row('one')])
  fake.postData.mockRejectedValueOnce(new Error('offline'))
  await page.find('textarea').setValue('2x=8\nx=4')
  await page.find('.primary-btn').trigger('click')
  await flushPromises()
  expect(fake.postData).toHaveBeenCalledWith(
    '/students/assignments/one/attempts',
    expect.objectContaining({ answer: '2x=8\nx=4', steps: ['2x=8', 'x=4'] }),
  )
  expect((page.find('textarea').element as HTMLTextAreaElement).value).toBe('2x=8\nx=4')
  expect(page.find('.primary-btn').attributes('disabled')).toBeUndefined()
})
it('successful submission leaves the same card open with its real review state', async () => {
  const page = await make([row('one'), row('two')])
  await page.findAll('textarea')[0].setValue('x=4')
  fake.postData.mockResolvedValueOnce({ entered_review_queue: true })
  fake.getData.mockResolvedValueOnce([row('one', 'review_pending'), row('two')])
  await page.findAll('.primary-btn')[0].trigger('click')
  await flushPromises()
  const cards = page.findAll('.assignment-card')
  expect(cards[0].find('.assignment-body').isVisible()).toBe(true)
  expect(cards[0].text()).toContain('作答已提交，等待教师核对。')
  expect(cards[1].find('.assignment-body').isVisible()).toBe(false)
  expect(page.text()).toContain('待完成 1 项')
})
