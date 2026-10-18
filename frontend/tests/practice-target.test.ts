import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import Practice from '../src/pages/practice/practice.vue'
const fake = vi.hoisted(() => ({ postData: vi.fn(), go: vi.fn(), load: (_: any) => {} }))
vi.mock('@dcloudio/uni-app', () => ({ onLoad: (fn: any) => (fake.load = fn) }))
vi.mock('../src/api/index.js', () => ({ postData: fake.postData, mediaUrl: (x: string) => x }))
vi.mock('../src/utils/navigation.js', () => ({ go: fake.go }))
let wrapper: ReturnType<typeof mount> | undefined
function make() {
  wrapper = mount(Practice, {
    global: {
      stubs: {
        'app-header': true,
        'state-panel': true,
        'math-text': { props: ['text'], template: '<span>{{text}}</span>' },
        'written-answer': {
          props: ['modelValue'],
          template:
            '<textarea :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
        },
      },
    },
  })
  fake.load({ id: 'source' })
  return wrapper
}
beforeEach(() => {
  fake.postData.mockReset()
  fake.go.mockReset()
})
afterEach(() => wrapper?.unmount())
it('缺少目标时提供核对错题的行动，不让学生反复空重试', async () => {
  fake.postData.mockRejectedValueOnce(
    Object.assign(new Error('请先分析这道题'), { statusCode: 422 }),
  )
  const page = make()
  await flushPromises()
  expect(page.text()).toContain('先确认这道题的知识点')
  const button = page.findAll('button').find((x) => x.text() === '核对这道错题')!
  await button.trigger('click')
  expect(fake.go).toHaveBeenCalledWith('/pages/detail/detail?id=source')
})
it('旧推荐被拒绝时可重新匹配，不显示已判对或掌握更新', async () => {
  fake.postData.mockResolvedValueOnce({
    question_id: 'q',
    subject: '数学',
    question_type: '填空题',
    stem: '3x=12',
    options: [],
  })
  const page = make()
  await flushPromises()
  await page.find('textarea').setValue('x=4')
  fake.postData.mockRejectedValueOnce(
    Object.assign(new Error('这道练习与当前学习目标不匹配'), { statusCode: 409 }),
  )
  await page.find('.primary-btn').trigger('click')
  await flushPromises()
  expect(page.text()).toContain('重新匹配')
  expect(page.find('.result-card').exists()).toBe(false)
})
it('普通网络失败仍保留当前作答', async () => {
  fake.postData.mockResolvedValueOnce({
    question_id: 'q',
    subject: '数学',
    question_type: '填空题',
    stem: '3x=12',
    options: [],
  })
  const page = make()
  await flushPromises()
  await page.find('textarea').setValue('x=4')
  fake.postData.mockRejectedValueOnce(new Error('network'))
  await page.find('.primary-btn').trigger('click')
  await flushPromises()
  expect((page.find('textarea').element as HTMLTextAreaElement).value).toBe('x=4')
})
