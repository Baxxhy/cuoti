import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import Review from '../src/pages/review/review.vue'
const fake = vi.hoisted(() => ({
  getData: vi.fn(),
  postData: vi.fn(),
  go: vi.fn(),
  hooks: {} as Record<string, any>,
}))
vi.mock('@dcloudio/uni-app', () => ({
  onLoad: (fn: any) => (fake.hooks.load = fn),
  onShow: (fn: any) => (fake.hooks.show = fn),
  onHide: (fn: any) => (fake.hooks.hide = fn),
  onUnload: (fn: any) => (fake.hooks.unload = fn),
}))
vi.mock('../src/api/index.js', () => ({ getData: fake.getData, postData: fake.postData }))
vi.mock('../src/utils/navigation.js', () => ({ go: fake.go }))
const plan = (version = 'v1', receipt: any = null) => ({
  id: 'plan-1',
  source_version: version,
  pending_attempt: receipt,
  question: { id: 'q1', subject: '数学', question_text: '2x+3=11', options: [] },
})
const receipt = {
  attempt_id: 'receipt-1',
  request_id: 'request-1',
  can_update_learning: true,
  correct: true,
  student_answer: 'x=4',
  feedback: '回答正确',
  expected_answer: 'x=4',
}
let page: ReturnType<typeof mount>,
  storage: Map<string, any>,
  rows: any[],
  records: any[],
  user: string
async function make(query = {}) {
  page = mount(Review, {
    global: {
      stubs: {
        checkbox: true,
        'checkbox-group': true,
        radio: true,
        'radio-group': true,
        'app-header': true,
        'state-panel': true,
        'uni-icons': true,
        'math-text': { props: ['text'], template: '<span>{{text}}</span>' },
        'written-answer': {
          name: 'WrittenAnswer',
          props: ['modelValue'],
          template:
            '<textarea :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
          methods: { reset() {}, restore() {} },
        },
      },
    },
  })
  fake.hooks.load(query)
  fake.hooks.show()
  await flushPromises()
  return page
}
beforeEach(() => {
  storage = new Map([['minddimension_access_token', 'token-a']])
  rows = [plan()]
  records = []
  user = 'user-a'
  fake.getData.mockReset().mockImplementation(async (path: string) => {
    if (path === '/auth/me') return { id: user }
    if (path === '/reviews/today') return structuredClone(rows)
    if (path === '/reviews/history') return records
    if (path === '/dashboard') return { misconceptions: [{ label: '移项' }] }
    throw new Error(path)
  })
  fake.postData.mockReset()
  fake.go.mockReset()
  vi.stubGlobal('uni', {
    getStorageSync: (key: string) => storage.get(key),
    setStorageSync: (key: string, value: any) => storage.set(key, structuredClone(value)),
    removeStorageSync: (key: string) => storage.delete(key),
  })
})
afterEach(() => {
  page?.unmount()
  vi.unstubAllGlobals()
})
it('文字草稿刷新恢复，历史和巩固建议默认不请求', async () => {
  await make()
  await page.find('textarea').setValue('2x=8\nx=4')
  page.unmount()
  await make()
  expect((page.find('textarea').element as HTMLTextAreaElement).value).toBe('2x=8\nx=4')
  expect(
    fake.getData.mock.calls.some(([path]) => path === '/reviews/history' || path === '/dashboard'),
  ).toBe(false)
  expect(
    page.findAll('.history-toggle').every((item) => item.attributes('aria-expanded') === 'false'),
  ).toBe(true)
})
it('不同账号和题目版本不恢复旧文字', async () => {
  await make()
  await page.find('textarea').setValue('旧答案')
  page.unmount()
  rows = [plan('v2')]
  await make()
  expect((page.find('textarea').element as HTMLTextAreaElement).value).toBe('')
  await page.find('textarea').setValue('另一个版本')
  page.unmount()
  user = 'user-b'
  storage.set('minddimension_access_token', 'token-b')
  await make()
  expect((page.find('textarea').element as HTMLTextAreaElement).value).toBe('')
})
it('提交失败持续反馈，刷新后重试复用同一请求编号', async () => {
  await make()
  await page.find('textarea').setValue('x=4')
  fake.postData.mockRejectedValueOnce(new Error('连接中断，请重试'))
  await page.find('.primary-btn').trigger('click')
  await flushPromises()
  expect(page.find('[role="alert"]').text()).toContain('连接中断')
  const first = fake.postData.mock.calls[0][1]
  page.unmount()
  await make()
  fake.postData.mockResolvedValueOnce(receipt)
  await page.find('.primary-btn').trigger('click')
  await flushPromises()
  expect(fake.postData.mock.calls[1][1]).toEqual(first)
  expect(page.find('.grade-grid').exists()).toBe(true)
})
it('判题结果从服务器恢复；不依靠本地结果开放自评', async () => {
  rows = [plan('v1', receipt)]
  await make()
  expect(page.find('.answer-result').text()).toContain('回答正确')
  expect(page.find('textarea').exists()).toBe(false)
  expect(page.find('.grade-grid').exists()).toBe(true)
  expect(fake.postData).not.toHaveBeenCalled()
})
it('丢失判题回执后从服务器找回同一次结果', async () => {
  await make()
  await page.find('textarea').setValue('x=4')
  fake.postData.mockImplementationOnce(async (_path, payload) => {
    rows = [plan('v1', { ...receipt, request_id: payload.request_id })]
    throw new Error('回执中断')
  })
  await page.find('.primary-btn').trigger('click')
  await flushPromises()
  expect(page.find('.grade-grid').exists()).toBe(true)
  expect(page.find('[role="alert"]').exists()).toBe(false)
  expect(page.text()).toContain('已找回刚才的判题结果')
})
it('评价失败保留判题，已成功但丢失回执时从历史确认并移除待办', async () => {
  rows = [plan('v1', receipt)]
  await make()
  fake.postData.mockRejectedValueOnce(new Error('评价连接中断'))
  await page.findAll('.grade-grid button')[2].trigger('click')
  await flushPromises()
  expect(page.find('[role="alert"]').text()).toContain('评价连接中断')
  expect(page.find('.grade-grid').exists()).toBe(true)
  fake.postData.mockImplementationOnce(async () => {
    records = [{ id: receipt.attempt_id, plan: { id: 'plan-1', status: 'completed' } }]
    rows = []
    throw new Error('回执中断')
  })
  await page.findAll('.grade-grid button')[2].trigger('click')
  await flushPromises()
  expect(page.text()).toContain('本次复习已记录')
  expect(page.text()).toContain('今天没有待复习题目')
})
it('离开后迟到提交不覆盖返回页，返回重新读取服务器', async () => {
  await make()
  await page.find('textarea').setValue('x=4')
  let finish: any
  fake.postData.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finish = resolve
      }),
  )
  await page.find('.primary-btn').trigger('click')
  await flushPromises()
  fake.hooks.hide()
  fake.hooks.show()
  await flushPromises()
  finish(receipt)
  await flushPromises()
  expect(page.find('.grade-grid').exists()).toBe(false)
  expect((page.find('textarea').element as HTMLTextAreaElement).value).toBe('x=4')
})
it('待核对结果修改后的新草稿刷新保留，不被旧结果覆盖', async () => {
  rows = [plan('v1', { ...receipt, can_update_learning: false })]
  await make()
  await page.find('.review-card .secondary-btn').trigger('click')
  await page.find('textarea').setValue('重新整理的答案')
  page.unmount()
  await make()
  expect((page.find('textarea').element as HTMLTextAreaElement).value).toBe('重新整理的答案')
  expect(page.find('.answer-result').exists()).toBe(false)
})

it('自评等待回执时声明不可用，失败核对后才恢复操作', async () => {
  rows = [plan('v1', receipt)]
  await make()
  let reject: (reason: Error) => void = () => {}
  fake.postData.mockImplementationOnce(
    () =>
      new Promise((_resolve, fail) => {
        reject = fail
      }),
  )
  await page.findAll('.grade-grid button')[2].trigger('click')
  await flushPromises()
  expect(
    page
      .findAll('.grade-grid button')
      .every((button) => button.attributes('aria-disabled') === 'true'),
  ).toBe(true)
  reject(new Error('连接中断'))
  await flushPromises()
  expect(
    page
      .findAll('.grade-grid button')
      .every((button) => button.attributes('aria-disabled') === 'false'),
  ).toBe(true)
})

function queued(id: string, text: string, result: any = null) {
  return {
    ...plan('v1', result),
    id,
    question: { ...plan().question, id: `q-${id}`, question_text: text },
  }
}
it('两题切换各自保留文字，不提交答案或评价', async () => {
  rows = [queued('one', '第一题'), queued('two', '第二题')]
  await make()
  await page.find('textarea').setValue('第一题草稿')
  await page.find('.queue-next').trigger('click')
  await flushPromises()
  expect(page.findAll('textarea')).toHaveLength(1)
  expect(page.find('.review-question').text()).toBe('第二题')
  await page.find('textarea').setValue('第二题草稿')
  await page.find('.queue-previous').trigger('click')
  await flushPromises()
  expect((page.find('textarea').element as HTMLTextAreaElement).value).toBe('第一题草稿')
  expect(page.find('.queue-previous').attributes('aria-disabled')).toBe('true')
  await page.find('.queue-next').trigger('click')
  await flushPromises()
  expect((page.find('textarea').element as HTMLTextAreaElement).value).toBe('第二题草稿')
  expect(page.find('.queue-next').attributes('aria-disabled')).toBe('true')
  expect(fake.postData).not.toHaveBeenCalled()
})
it('存储失败仍在本页保留各题草稿，切换不依赖网络', async () => {
  rows = [queued('one', '第一题'), queued('two', '第二题')]
  ;(globalThis as any).uni.setStorageSync = () => {
    throw new Error('quota')
  }
  await make()
  await page.find('textarea').setValue('缓存不可用时的作答')
  const reads = fake.getData.mock.calls.length
  await page.find('.queue-next').trigger('click')
  await flushPromises()
  await page.find('textarea').setValue('另一题的作答')
  await page.find('.queue-previous').trigger('click')
  await flushPromises()
  expect((page.find('textarea').element as HTMLTextAreaElement).value).toBe('缓存不可用时的作答')
  expect(page.text()).toContain('请保持此页打开后提交')
  expect(fake.getData.mock.calls).toHaveLength(reads)
  expect(fake.postData).not.toHaveBeenCalled()
})
it('普通入口记住当前题，指定题链接优先，来源变更不恢复旧草稿', async () => {
  rows = [queued('one', '第一题'), queued('two', '第二题')]
  await make()
  await page.find('.queue-next').trigger('click')
  await flushPromises()
  await page.find('textarea').setValue('第二题旧版本草稿')
  page.unmount()
  await make()
  expect(page.find('.review-question').text()).toBe('第二题')
  expect((page.find('textarea').element as HTMLTextAreaElement).value).toBe('第二题旧版本草稿')
  page.unmount()
  rows[1].source_version = 'v2'
  await make()
  expect(page.find('.review-question').text()).toBe('第二题')
  expect((page.find('textarea').element as HTMLTextAreaElement).value).toBe('')
  page.unmount()
  await make({ plan: 'one' })
  expect(page.find('.review-question').text()).toBe('第一题')
})
it('照片识别和判题在途时禁止切题，回执后才能继续', async () => {
  rows = [queued('one', '第一题'), queued('two', '第二题')]
  await make()
  const writer = page.findComponent({ name: 'WrittenAnswer' })
  writer.vm.$emit('uploading-change', true)
  await flushPromises()
  await page.find('.queue-next').trigger('click')
  await flushPromises()
  expect(page.find('.review-question').text()).toBe('第一题')
  writer.vm.$emit('uploading-change', false)
  await page.find('textarea').setValue('x=4')
  let finish: any
  fake.postData.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finish = resolve
      }),
  )
  await page.find('.primary-btn').trigger('click')
  await flushPromises()
  expect(page.find('.queue-next').attributes('aria-disabled')).toBe('true')
  await page.find('.queue-next').trigger('click')
  await flushPromises()
  expect(page.find('.review-question').text()).toBe('第一题')
  finish(receipt)
  await flushPromises()
  await page.find('.queue-next').trigger('click')
  await flushPromises()
  expect(page.find('.review-question').text()).toBe('第二题')
})
it('待核对结果修改后切题返回仍是新草稿，不重新显示旧判题', async () => {
  rows = [
    queued('one', '第一题', { ...receipt, can_update_learning: false }),
    queued('two', '第二题'),
  ]
  await make()
  await page.find('.review-card .secondary-btn').trigger('click')
  await page.find('textarea').setValue('重写后的文字')
  await page.find('.queue-next').trigger('click')
  await flushPromises()
  await page.find('.queue-previous').trigger('click')
  await flushPromises()
  expect(page.find('.answer-result').exists()).toBe(false)
  expect((page.find('textarea').element as HTMLTextAreaElement).value).toBe('重写后的文字')
})
it('完成队列中间一题后继续下一题，不跳回首题', async () => {
  const first = queued('one', '第一题'),
    next = queued('three', '第三题')
  rows = [first, queued('two', '第二题', receipt), next]
  await make({ plan: 'two' })
  fake.postData.mockImplementationOnce(async () => {
    rows = [first, next]
    return {}
  })
  await page.findAll('.grade-grid button')[2].trigger('click')
  await flushPromises()
  expect(page.find('.review-question').text()).toBe('第三题')
  expect(page.text()).toContain('本次复习已记录')
})

it('复习失败可回原题学习，保留作答并携带返回的复习计划', async () => {
  await make()
  await page.find('textarea').setValue('原来的复习作答')
  fake.postData.mockRejectedValueOnce(new Error('请先完成本题分析'))
  await page.find('.primary-btn').trigger('click')
  await flushPromises()
  await page.find('.review-origin').trigger('click')
  expect(fake.go).toHaveBeenCalledWith('/pages/detail/detail?id=q1&review=plan-1')
  fake.hooks.hide()
  fake.hooks.show()
  await flushPromises()
  expect((page.find('textarea').element as HTMLTextAreaElement).value).toBe('原来的复习作答')
})
it('待核对结果可回原题，正常独立作答不额外出现入口', async () => {
  await make()
  expect(page.find('.review-origin').exists()).toBe(false)
  page.unmount()
  rows = [plan('v1', { ...receipt, can_update_learning: false })]
  await make()
  expect(page.find('.review-origin').text()).toBe('回原题学习')
})
it('来源更新后旧文字需显式使用，旧照片和请求编号不进入新作答', async () => {
  await make()
  await page.find('textarea').setValue('x=4')
  page.findComponent({ name: 'WrittenAnswer' }).vm.$emit('handwriting-change', {
    image_url: '/old-photo.jpg',
    recognition: { final_answer: 'x=4' },
  })
  fake.postData.mockRejectedValueOnce(new Error('断网'))
  await page.find('.primary-btn').trigger('click')
  await flushPromises()
  const oldId = fake.postData.mock.calls[0][1].request_id
  fake.hooks.hide()
  rows = [plan('v2')]
  fake.hooks.show()
  await flushPromises()
  expect((page.find('textarea').element as HTMLTextAreaElement).value).toBe('')
  expect(page.find('.previous-text').exists()).toBe(false)
  await page.find('.previous-toggle').trigger('click')
  expect(page.find('.previous-text').text()).toBe('x=4')
  await page.find('.use-previous').trigger('click')
  fake.postData.mockResolvedValueOnce(receipt)
  await page.find('.primary-btn').trigger('click')
  await flushPromises()
  const next = fake.postData.mock.calls[1][1]
  expect(next).toMatchObject({
    answer: 'x=4',
    source_version: 'v2',
    handwriting_image_url: '',
    handwriting_recognition: null,
  })
  expect(next.request_id).not.toBe(oldId)
})
it('旧文字跨刷新保留，已有新作答不被替换，可以不再保留旧稿', async () => {
  await make()
  await page.find('textarea').setValue('旧文字')
  page.unmount()
  rows = [plan('v2')]
  await make()
  page.unmount()
  await make()
  await page.find('.previous-toggle').trigger('click')
  expect(page.find('.previous-text').text()).toBe('旧文字')
  await page.find('textarea').setValue('新文字')
  expect(page.find('.use-previous').exists()).toBe(false)
  await page.find('.previous-dismiss').trigger('click')
  expect((page.find('textarea').element as HTMLTextAreaElement).value).toBe('新文字')
  page.unmount()
  await make()
  expect(page.find('.previous-draft').exists()).toBe(false)
  expect((page.find('textarea').element as HTMLTextAreaElement).value).toBe('新文字')
})
it('旧草稿不会跨账号显示', async () => {
  await make()
  await page.find('textarea').setValue('仅旧账号的文字')
  page.unmount()
  rows = [plan('v2')]
  user = 'user-b'
  storage.set('minddimension_access_token', 'token-b')
  await make()
  expect(page.find('.previous-draft').exists()).toBe(false)
  expect((page.find('textarea').element as HTMLTextAreaElement).value).toBe('')
})

it('从原题返回时旧计划消失，说明待办变化并保留原题入口和旧文字', async () => {
  await make()
  await page.find('textarea').setValue('原题学习前的文字')
  fake.postData.mockRejectedValueOnce(new Error('需要先分析'))
  await page.find('.primary-btn').trigger('click')
  await flushPromises()
  await page.find('.review-origin').trigger('click')
  fake.hooks.hide()
  rows = []
  fake.hooks.show()
  await flushPromises()
  expect(page.text()).toContain('这条复习安排已不在待办中')
  expect(page.text()).not.toContain('今天没有待复习题目')
  await page.find('.origin-unavailable .previous-toggle').trigger('click')
  expect(page.find('.origin-unavailable .previous-text').text()).toBe('原题学习前的文字')
  await page.find('.missing-origin').trigger('click')
  expect(fake.go).toHaveBeenLastCalledWith('/pages/detail/detail?id=q1&review=plan-1')
})
it('计划消失后其他待办仍可作答，旧文字不会进入其他题输入', async () => {
  await make()
  await page.find('textarea').setValue('不能带给其他题的文字')
  fake.postData.mockRejectedValueOnce(new Error('需要先分析'))
  await page.find('.primary-btn').trigger('click')
  await flushPromises()
  await page.find('.review-origin').trigger('click')
  fake.hooks.hide()
  rows = [queued('other', '另一道题')]
  fake.hooks.show()
  await flushPromises()
  expect(page.find('.review-question').text()).toBe('另一道题')
  expect((page.find('textarea').element as HTMLTextAreaElement).value).toBe('')
  expect(page.find('.missing-origin').exists()).toBe(true)
})
