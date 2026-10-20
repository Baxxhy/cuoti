import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import Teacher from '../src/components/knowledge-teacher/knowledge-teacher.vue'
const api = vi.hoisted(() => ({ getData: vi.fn(), postData: vi.fn() }))
vi.mock('../src/api/index.js', () => api)
let owner = 'student-a'
const lesson = {
  id: 'lesson-1',
  prompt: '为什么',
  result: {
    explanation: '等式两边做相同的运算，等式仍然成立。',
    key_points: ['两边同时运算'],
    check_question: '两边同时加3会怎样？',
    sources: [{ name: '等式性质' }],
  },
}
let page: ReturnType<typeof mount>
beforeEach(() => {
  vi.resetAllMocks()
  owner = 'student-a'
  api.getData.mockResolvedValue([])
  vi.stubGlobal('uni', { getStorageSync: () => owner })
  page = mount(Teacher, {
    props: { code: 'equation' },
    global: {
      stubs: {
        'uni-icons': true,
        'math-text': { props: ['text'], template: '<span>{{text}}</span>' },
      },
    },
  })
})
afterEach(() => {
  page.unmount()
  vi.unstubAllGlobals()
})
async function open() {
  await page.find('button').trigger('click')
  await flushPromises()
}
const send = () => page.find('.primary-btn').trigger('click')
it('打开才读取历史；失败重试复用请求编号，成功后保留记录', async () => {
  expect(api.getData).not.toHaveBeenCalled()
  await open()
  await page.find('textarea').setValue('为什么')
  api.postData.mockRejectedValueOnce(new Error('暂时不可用')).mockResolvedValueOnce(lesson)
  await send()
  await flushPromises()
  expect((page.find('textarea').element as HTMLTextAreaElement).value).toBe('为什么')
  await send()
  await flushPromises()
  expect(api.postData.mock.calls[0][1].request_id).toBe(api.postData.mock.calls[1][1].request_id)
  expect(page.text()).toContain('两边同时运算')
  expect(api.postData.mock.calls.every(([path]) => path.endsWith('/lessons'))).toBe(true)
})
it('来源冲突后保留问题，下一次提交使用新编号，避免反复撞上旧版本', async () => {
  await open()
  await page.find('textarea').setValue('为什么')
  api.postData
    .mockRejectedValueOnce(
      Object.assign(new Error('知识内容已更新，请重新提问'), { statusCode: 409 }),
    )
    .mockResolvedValueOnce(lesson)
  await send()
  await flushPromises()
  expect((page.find('textarea').element as HTMLTextAreaElement).value).toBe('为什么')
  await send()
  await flushPromises()
  expect(api.postData.mock.calls[0][1].request_id).not.toBe(
    api.postData.mock.calls[1][1].request_id,
  )
  expect(page.text()).toContain('两边同时运算')
})
it('知识卡切换后忽略迟到回答，不把上一张讲解带到新知识点', async () => {
  await open()
  let resolve: (value: any) => void
  api.postData.mockImplementation(
    () =>
      new Promise((r) => {
        resolve = r
      }),
  )
  await send()
  await page.setProps({ code: 'fraction' })
  resolve!(lesson)
  await flushPromises()
  await open()
  expect(page.text()).not.toContain('两边同时运算')
  expect(api.getData).toHaveBeenLastCalledWith('/knowledge/cards/fraction/lessons')
})
it('账号变化后不显示旧账号的迟到记录', async () => {
  let resolve: (value: any) => void
  api.getData.mockImplementation(
    () =>
      new Promise((r) => {
        resolve = r
      }),
  )
  await page.find('button').trigger('click')
  owner = 'student-b'
  resolve!([lesson])
  await flushPromises()
  expect(page.text()).not.toContain('两边同时运算')
})
