import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import Paper from '../src/pages/paper/paper-center.vue'

const fake = vi.hoisted(() => ({
  getData: vi.fn(),
  postData: vi.fn(),
  patchData: vi.fn(),
  deleteData: vi.fn(),
  hooks: {} as Record<string, any>,
  toast: vi.fn(),
  modal: vi.fn(),
}))
vi.mock('@dcloudio/uni-app', () => ({
  onLoad: (fn: any) => (fake.hooks.load = fn),
  onUnload: (fn: any) => (fake.hooks.unload = fn),
}))
vi.mock('../src/api/index.js', () => fake)
vi.mock('../src/utils/export-file.js', () => ({ openExportFile: vi.fn() }))
const paper = (id: string) => ({
  id,
  title: `试卷${id}`,
  exports: [],
  items: [{ id: 'item-1', question_id: 'q-1', score: 10, question: { question_text: '2x=8' } }],
})
let page: ReturnType<typeof mount>
async function make() {
  page = mount(Paper, {
    global: { stubs: { 'app-header': true, 'uni-icons': true, 'state-panel': true, slider: true } },
  })
  fake.hooks.load({})
  await flushPromises()
}
async function open(id = 'a') {
  await page
    .findAll('.history-paper')
    .find((row) => row.text().includes(`试卷${id}`))!
    .trigger('click')
  await flushPromises()
}
const button = (label: string) =>
  page.findAll('button').find((item) => item.text().includes(label))!
beforeEach(() => {
  vi.resetAllMocks()
  fake.getData.mockImplementation(async (url: string) => {
    if (url === '/papers') return [paper('a'), paper('b')]
    if (url.startsWith('/papers/candidates')) return [{ id: 'q-1', question_text: '2x=8' }]
    return paper(url.split('/').pop()!)
  })
  vi.stubGlobal('uni', { showToast: fake.toast, showModal: fake.modal })
})
afterEach(() => {
  page?.unmount()
  vi.unstubAllGlobals()
})

it('后返回的旧试卷不能覆盖最近选择，等待期间编辑被禁用', async () => {
  await make()
  await open()
  const resolvers: Record<string, any> = {}
  fake.getData.mockImplementation(
    (url: string) =>
      new Promise((resolve) => {
        resolvers[url] = resolve
      }),
  )
  await open('a')
  expect(page.find('.editor-title input').attributes('disabled')).toBeDefined()
  await open('b')
  resolvers['/papers/b'](paper('b'))
  await flushPromises()
  resolvers['/papers/a'](paper('a'))
  await flushPromises()
  expect((page.find('.editor-title input').element as HTMLInputElement).value).toBe('试卷b')
  expect(page.find('.operation-status').exists()).toBe(false)
})

it('旧打开请求失败不覆盖当前成功试卷的状态，卸载后的回执也不生效', async () => {
  await make()
  let rejectOld: any, resolveLate: any
  fake.getData.mockImplementationOnce(
    () =>
      new Promise((_, reject) => {
        rejectOld = reject
      }),
  )
  await open('a')
  await open('b')
  rejectOld(new Error('旧请求失败'))
  await flushPromises()
  expect(page.find('[role="alert"]').exists()).toBe(false)
  fake.getData.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        resolveLate = resolve
      }),
  )
  await open('a')
  fake.hooks.unload()
  resolveLate(paper('a'))
  await flushPromises()
  expect((page.find('.editor-title input').element as HTMLInputElement).value).toBe('试卷b')
})

it('保存失败持续说明错误并保留标题与分值，重试成功清除错误', async () => {
  await make()
  await open()
  await page.find('.editor-title input').setValue('我的复习卷')
  await page.find('.score-edit input').setValue('15')
  fake.patchData.mockRejectedValueOnce(new Error('保存连接中断'))
  await button('保存名称').trigger('click')
  await flushPromises()
  expect(page.find('[role="alert"]').text()).toContain('保存连接中断')
  expect((page.find('.editor-title input').element as HTMLInputElement).value).toBe('我的复习卷')
  expect((page.find('.score-edit input').element as HTMLInputElement).value).toBe('15')
  fake.patchData.mockResolvedValueOnce({ ...paper('a'), title: '我的复习卷' })
  await button('保存名称').trigger('click')
  await flushPromises()
  expect(page.find('[role="alert"]').exists()).toBe(false)
  expect(fake.patchData.mock.calls[1][1]).toMatchObject({
    title: '我的复习卷',
    items: [{ question_id: 'q-1', score: 15 }],
  })
})

it('导出生成后读取失败不宣称完成，可重新打开实际记录', async () => {
  await make()
  await open()
  fake.patchData.mockResolvedValueOnce(paper('a'))
  fake.postData.mockResolvedValueOnce({})
  const normalGet = fake.getData.getMockImplementation()!
  fake.getData.mockImplementation((url: string) =>
    url === '/papers/a' ? Promise.reject(new Error('读取中断')) : normalGet(url),
  )
  await button('题目 PDF').trigger('click')
  await flushPromises()
  expect(page.find('[role="alert"]').text()).toContain('重新选择这份试卷')
  expect(fake.toast).not.toHaveBeenCalledWith(expect.objectContaining({ title: '导出已生成' }))
  expect(fake.postData).toHaveBeenCalledTimes(1)
})

it('创建失败提供持续反馈，所选题目保留', async () => {
  await make()
  await page.find('.candidate').trigger('click')
  fake.postData.mockRejectedValueOnce(new Error('创建连接中断'))
  await button('创建试卷').trigger('click')
  await flushPromises()
  expect(page.find('[role="alert"]').text()).toContain('创建连接中断')
  expect(page.findAll('.candidate.selected')).toHaveLength(1)
})

it('删除失败可重试；确认框打开后切换试卷不删除原试卷', async () => {
  await make()
  await open()
  await button('删除').trigger('click')
  await open('b')
  await fake.modal.mock.calls[0][0].success({ confirm: true })
  expect(fake.deleteData).not.toHaveBeenCalled()
  await button('删除').trigger('click')
  fake.deleteData.mockRejectedValueOnce(new Error('删除连接中断'))
  await fake.modal.mock.calls[1][0].success({ confirm: true })
  await flushPromises()
  expect(page.find('[role="alert"]').text()).toContain('删除连接中断')
  expect((page.find('.editor-title input').element as HTMLInputElement).value).toBe('试卷b')
  await button('删除').trigger('click')
  fake.deleteData.mockResolvedValueOnce({})
  await fake.modal.mock.calls[2][0].success({ confirm: true })
  await flushPromises()
  expect(page.find('.paper-editor').exists()).toBe(false)
  expect(page.findAll('.history-paper')).toHaveLength(1)
})

it('组卷候选、知识点与试卷预览渲染完整公式，选择和排序后仍正确', async () => {
  const text = String.raw`在 $\frac{1}{5}$、$\frac{1}{6}$、$\frac{1}{10}$ 三个分数中，最大的是()，最小的是()。`
  const geometry = String.raw`过点 $A_1$ 作 $x$ 轴的垂线交 $y=\sqrt{3}x$ 于 $B_1$；按此做法进行下去，求 $A_5$ 的坐标。完整题干末尾。`
  const value = {
    ...paper('a'),
    items: [
      { id: 'item-1', question_id: 'q-1', score: 10, question: { question_text: text } },
      { id: 'item-2', question_id: 'q-2', score: 10, question: { question_text: geometry } },
    ],
  }
  fake.getData.mockImplementation(async (url: string) => {
    if (url === '/papers') return [value]
    if (url.startsWith('/papers/candidates'))
      return [
        { id: 'q-1', question_text: text, knowledge_points: [String.raw`比较 $\frac{1}{n}$`] },
      ]
    return value
  })
  await make()
  expect(page.find('.candidate').findAll('.mfrac')).toHaveLength(4)
  expect(page.find('.candidate .math-unparsed').exists()).toBe(false)
  await page.find('.candidate').trigger('click')
  expect(button('创建试卷').text()).toContain('1题')
  await open()
  expect(page.findAll('.paper-item')[0].findAll('.mfrac')).toHaveLength(3)
  expect(page.findAll('.paper-item')[1].find('.sqrt').exists()).toBe(true)
  expect(page.findAll('.paper-item')[1].text()).toContain('完整题干末尾。')
  await page.find('[aria-label="第2题上移"]').trigger('click')
  expect(page.findAll('.paper-item')[0].find('.sqrt').exists()).toBe(true)
  expect(page.find('.katex-display').exists()).toBe(false)
})

it('空知识点和空年级显示待分析，不把null或undefined拼进界面', async () => {
  fake.getData.mockImplementation(async (url: string) =>
    url.startsWith('/papers/candidates')
      ? [
          {
            id: 'q-null',
            subject: '数学',
            grade: null,
            knowledge_points: [null, 'null', 'undefined', ''],
          },
        ]
      : [],
  )
  await make()
  expect(page.find('.candidate .list-desc').text()).toBe('数学 · 知识点待分析')
  expect(page.find('.candidate .list-desc').text()).not.toMatch(/null|undefined/)
})

it('分值调节器居中输入、增减和直接输入均能更新总分，并遵守边界', async () => {
  await make()
  await open()
  await page.find('[aria-label="第1题加1分"]').trigger('click')
  expect((page.find('.paper-score-input').element as HTMLInputElement).value).toBe('11')
  expect(page.find('.total-score').text()).toContain('11')
  await page.find('[aria-label="第1题减1分"]').trigger('click')
  expect((page.find('.paper-score-input').element as HTMLInputElement).value).toBe('10')
  await page.find('.paper-score-input').setValue('100')
  expect(page.find('[aria-label="第1题加1分"]').attributes('disabled')).toBeDefined()
  await page.find('.paper-score-input').setValue('1')
  expect(page.find('[aria-label="第1题减1分"]').attributes('disabled')).toBeDefined()
})

it('导出答案前补齐缺失解析，刷新知识点后才请求PDF，不重复分析已有题目', async () => {
  const incomplete = {
    ...paper('a'),
    items: [
      {
        ...paper('a').items[0],
        analysis_ready: false,
        question: { question_text: '2x=8', confirmed: true },
      },
    ],
  }
  const complete = {
    ...incomplete,
    items: incomplete.items.map((item) => ({ ...item, analysis_ready: true })),
  }
  await make()
  fake.getData.mockResolvedValueOnce(incomplete)
  await open()
  fake.patchData.mockResolvedValueOnce(incomplete)
  const normal = fake.getData.getMockImplementation()!
  fake.getData.mockImplementation(async (url: string) =>
    url === '/papers/a' ? complete : normal(url),
  )
  fake.postData.mockResolvedValue({})
  await button('补齐解析并导出答案').trigger('click')
  await flushPromises()
  expect(fake.postData.mock.calls.map((call) => call[0])).toEqual([
    '/questions/q-1/analyze',
    '/papers/a/export',
  ])
  expect(fake.toast).toHaveBeenCalledWith(expect.objectContaining({ title: '导出已生成' }))
})

it('解析补齐失败时不生成空答案PDF，保留试卷和可重试状态', async () => {
  const incomplete = {
    ...paper('a'),
    items: [
      {
        ...paper('a').items[0],
        analysis_ready: false,
        question: { question_text: '2x=8', confirmed: true },
      },
    ],
  }
  await make()
  fake.getData.mockResolvedValueOnce(incomplete)
  await open()
  fake.patchData.mockResolvedValueOnce(incomplete)
  fake.postData.mockRejectedValueOnce(new Error('分析暂时不可用'))
  await button('补齐解析并导出答案').trigger('click')
  await flushPromises()
  expect(page.find('[role="alert"]').text()).toContain('分析暂时不可用')
  expect(fake.postData.mock.calls.map((call) => call[0])).toEqual(['/questions/q-1/analyze'])
  expect(page.find('.paper-editor').exists()).toBe(true)
})

it('未核对的题目不会自动确认或发送分析请求', async () => {
  const incomplete = {
    ...paper('a'),
    items: [
      {
        ...paper('a').items[0],
        analysis_ready: false,
        question: { question_text: '2x=8', confirmed: false },
      },
    ],
  }
  await make()
  fake.getData.mockResolvedValueOnce(incomplete)
  await open()
  fake.patchData.mockResolvedValueOnce(incomplete)
  await button('补齐解析并导出答案').trigger('click')
  await flushPromises()
  expect(page.find('[role="alert"]').text()).toContain('尚未核对')
  expect(fake.postData).not.toHaveBeenCalled()
})

it('模型返回后仍缺少解析时不导出空文件', async () => {
  const incomplete = {
    ...paper('a'),
    items: [
      {
        ...paper('a').items[0],
        analysis_ready: false,
        question: { question_text: '2x=8', confirmed: true },
      },
    ],
  }
  await make()
  fake.getData.mockResolvedValueOnce(incomplete)
  await open()
  fake.patchData.mockResolvedValueOnce(incomplete)
  const normal = fake.getData.getMockImplementation()!
  fake.getData.mockImplementation(async (url: string) =>
    url === '/papers/a' ? incomplete : normal(url),
  )
  fake.postData.mockResolvedValueOnce({})
  await button('补齐解析并导出答案').trigger('click')
  await flushPromises()
  expect(page.find('[role="alert"]').text()).toContain('部分题目的分析仍不完整')
  expect(fake.postData).toHaveBeenCalledTimes(1)
})
