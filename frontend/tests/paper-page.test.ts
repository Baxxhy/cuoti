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
