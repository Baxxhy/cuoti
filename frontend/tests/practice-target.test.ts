import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import Practice from '../src/pages/practice/practice.vue'
const fake = vi.hoisted(() => ({
  postData: vi.fn(),
  go: vi.fn(),
  load: (_: any) => {},
  leave: () => {},
}))
vi.mock('@dcloudio/uni-app', () => ({
  onLoad: (fn: any) => (fake.load = fn),
  onUnload: (fn: any) => (fake.leave = fn),
}))
vi.mock('../src/store/index.js', () => ({
  useAppStore: () => ({ user: { id: 'student' }, loadUser: vi.fn() }),
}))
vi.mock('../src/api/index.js', () => ({ postData: fake.postData, mediaUrl: (x: string) => x }))
vi.mock('../src/utils/navigation.js', () => ({ go: fake.go }))
let wrapper: ReturnType<typeof mount> | undefined
function make(query: { id: string; mode?: string } = { id: 'source' }) {
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
  fake.load(query)
  return wrapper
}
beforeEach(() => {
  const storage = new Map()
  vi.stubGlobal('uni', {
    getStorageSync: (key: string) => storage.get(key),
    setStorageSync: (key: string, value: unknown) => storage.set(key, value),
  })
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
  expect(page.text()).toContain('重新获取练习')
  expect((page.find('textarea').element as HTMLTextAreaElement).value).toBe('x=4')
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

it('刷新恢复同一道题的草稿，换题后不沿用旧答案', async () => {
  const question = { question_id: 'first', subject: '数学', stem: '3x=12', options: [] }
  fake.postData.mockResolvedValue(question)
  let page = make()
  await flushPromises()
  await page.find('textarea').setValue('x=4')
  fake.leave()
  page.unmount()
  page = make()
  await flushPromises()
  expect((page.find('textarea').element as HTMLTextAreaElement).value).toBe('x=4')
  fake.leave()
  page.unmount()
  fake.postData.mockResolvedValue({ ...question, question_id: 'second', stem: '3x=15' })
  page = make()
  await flushPromises()
  expect((page.find('textarea').element as HTMLTextAreaElement).value).toBe('')
})

it('判分后显示已提交答案，收起输入与拍照，避免修改后的文字与原判分混淆', async () => {
  fake.postData.mockResolvedValueOnce({
    question_id: 'q',
    subject: '数学',
    stem: '3x=12',
    options: [],
  })
  const page = make()
  await flushPromises()
  await page.find('textarea').setValue('x=4')
  fake.postData.mockResolvedValueOnce({
    correct: true,
    can_update_learning: true,
    feedback: '答对了。',
    answer: 'x=4',
  })
  await page.find('.primary-btn').trigger('click')
  await flushPromises()
  expect(page.find('textarea').exists()).toBe(false)
  expect(page.find('.submitted-answer').text()).toContain('x=4')
  expect(page.find('.result-card').text()).toContain('答对了')
})

it('切到变式后刷新仍请求变式并恢复已判定结果', async () => {
  window.history.replaceState({}, '', '/#/pages/practice/practice?id=source')
  const question = { question_id: 'q', subject: '数学', stem: '3x=12', options: [] }
  const receipt = { correct: true, can_update_learning: true, answer: 'x=4' }
  fake.postData.mockResolvedValueOnce(question).mockResolvedValueOnce(receipt)
  let page = make()
  await flushPromises()
  await page.find('textarea').setValue('x=4')
  await page.find('.primary-btn').trigger('click')
  await flushPromises()
  fake.postData.mockResolvedValueOnce({ ...question, question_id: 'variation' })
  await page.findAll('button').find((x) => x.text() === '换个问法试试')!.trigger('click')
  await flushPromises()
  expect(window.location.hash).toContain('mode=variation')
  expect(fake.postData).toHaveBeenLastCalledWith(
    '/practice/recommend',
    { mistake_id: 'source', mode: 'variation', force_new: true },
    expect.any(Object),
  )
  fake.leave()
  page.unmount()
  fake.postData.mockResolvedValueOnce({
    ...question,
    question_id: 'variation',
    previous_answer: 'x=4',
    previous_result: receipt,
  })
  const query = Object.fromEntries(new URLSearchParams(window.location.hash.split('?')[1]))
  page = make(query as { id: string; mode: string })
  await flushPromises()
  expect(fake.postData).toHaveBeenLastCalledWith(
    '/practice/recommend',
    { mistake_id: 'source', mode: 'variation', force_new: false },
    expect.any(Object),
  )
  expect(page.find('.result-card').text()).toContain('答对了')
  expect(page.find('.submitted-answer').text()).toContain('x=4')
})
