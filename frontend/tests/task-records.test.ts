import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import SelfCheck from '../src/components/self-check/self-check.vue'
import TaskHistory from '../src/components/task-history/task-history.vue'
const fake = vi.hoisted(() => ({ getData: vi.fn(), patchData: vi.fn(), deleteData: vi.fn() }))
vi.mock('../src/api/index.js', () => fake)
vi.mock('../src/store/index.js', () => ({ useAppStore: () => ({ user: { id: 'student-1' } }) }))
const task = { id: 'task-1', input_fingerprint: 'fp-1', status: 'completed', version: 8 }
const options = {
  global: { stubs: { 'math-text': { props: ['text'], template: '<span>{{text}}</span>' } } },
}
const empty = { note: null, version: 0, source_current: true, can_save: true }
const note = (text: string, version = 1) => ({
  ...empty,
  version,
  note: { id: 'note-1', text, version },
})
beforeEach(() => {
  vi.clearAllMocks()
  const storage = new Map()
  vi.stubGlobal('uni', {
    getStorageSync: (key: string) => storage.get(key),
    setStorageSync: (key: string, value: any) => storage.set(key, structuredClone(value)),
    showModal: vi.fn(),
  })
})
const button = (page: ReturnType<typeof mount>, text: string) =>
  page.findAll('button').find((item) => item.text() === text)!
describe('学生确认的自检要点', () => {
  it('主动展开才查询；保存失败保留输入、确认内容和版本，重试成功后回读', async () => {
    fake.getData.mockResolvedValue(empty)
    fake.patchData
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce(note('先检查符号'))
    let page = mount(SelfCheck, { ...options, props: { task } })
    expect(fake.getData).not.toHaveBeenCalled()
    await page.find('button').trigger('click')
    await flushPromises()
    await page.find('textarea').setValue('先检查符号')
    await button(page, '确认保存').trigger('click')
    await flushPromises()
    expect(page.find('textarea').element.value).toBe('先检查符号')
    expect(page.text()).toContain('草稿已保留')
    const body = fake.patchData.mock.calls[0][1]
    expect(body).toEqual({
      text: '先检查符号',
      confirmed: true,
      version: 0,
      input_fingerprint: 'fp-1',
    })
    page.unmount()
    page = mount(SelfCheck, { ...options, props: { task } })
    await page.find('button').trigger('click')
    await flushPromises()
    expect(page.find('textarea').element.value).toBe('先检查符号')
    await button(page, '确认保存').trigger('click')
    await flushPromises()
    expect(fake.patchData.mock.calls[1][1]).toEqual(body)
    expect(page.find('.saved-note').text()).toContain('先检查符号')
    expect(page.find('textarea').exists()).toBe(false)
    page.unmount()
  })
  it('冲突后重新读取最新要点并保留草稿，不静默覆盖', async () => {
    fake.getData
      .mockResolvedValueOnce(note('旧要点'))
      .mockResolvedValueOnce(note('另一处刚保存的要点', 2))
    fake.patchData.mockRejectedValue(Object.assign(new Error('conflict'), { statusCode: 409 }))
    const page = mount(SelfCheck, { ...options, props: { task } })
    await page.find('button').trigger('click')
    await flushPromises()
    await button(page, '编辑').trigger('click')
    await page.find('textarea').setValue('我的草稿')
    await button(page, '确认保存').trigger('click')
    await flushPromises()
    expect(page.text()).toContain('请重新核对')
    await button(page, '重新核对').trigger('click')
    await flushPromises()
    expect(page.find('.saved-note').text()).toContain('另一处刚保存的要点')
    expect(page.find('textarea').element.value).toBe('我的草稿')
    expect(fake.patchData).toHaveBeenCalledTimes(1)
    await button(page, '取消编辑').trigger('click')
    expect(page.find('textarea').exists()).toBe(false)
    page.unmount()
  })
  it('旧题要点保留可读，不能编辑；删除需确认且携带当前版本', async () => {
    fake.getData.mockResolvedValue({
      ...note('旧题提醒', 4),
      can_save: false,
      source_current: false,
    })
    fake.deleteData.mockResolvedValue({
      ...empty,
      version: 5,
      can_save: false,
      source_current: false,
    })
    const page = mount(SelfCheck, { ...options, props: { task: { ...task, status: 'stale' } } })
    await page.find('button').trigger('click')
    await flushPromises()
    expect(page.text()).toContain('历史提醒')
    expect(page.find('textarea').exists()).toBe(false)
    await button(page, '删除要点').trigger('click')
    expect(fake.deleteData).not.toHaveBeenCalled()
    await (globalThis as any).uni.showModal.mock.calls[0][0].success({ confirm: true })
    await flushPromises()
    expect(fake.deleteData).toHaveBeenCalledWith('/learning-tasks/task-1/self-check', {
      data: { version: 4 },
      silent: true,
    })
    expect(page.find('.saved-note').exists()).toBe(false)
    page.unmount()
  })
})
describe('按需展开的任务过程', () => {
  it.each([
    ['review_required', '仍需核对'],
    ['probably_correct', '可能正确，仍需核对'],
    ['probably_incorrect', '可能有误，仍需核对'],
  ])('保留未确认判定 %s 的核对提示', async (verdict, label) => {
    fake.getData.mockResolvedValue({
      items: [{ id: 'uncertain', kind: 'answer', status: 'applied', verdict, assisted: true }],
      has_more: false,
    })
    const page = mount(TaskHistory, { ...options, props: { task } })
    await page.find('button').trigger('click')
    await flushPromises()
    expect(page.find('.event').text()).toContain(label + ' · 使用过辅助')
    expect(page.find('.event').text()).not.toContain('本次结果已核对')
    page.unmount()
  })
  it('按时间显示学生动作；不显示私有字段，任务版本改变后才更新已展开的记录', async () => {
    fake.getData.mockResolvedValue({
      items: [
        {
          id: '2',
          kind: 'hint',
          status: 'applied',
          feedback: '检查移项',
          text: '',
          expected: 'secret-answer',
          phase: '',
          verdict: '',
        },
        {
          id: '1',
          kind: 'answer',
          status: 'applied',
          text: '11-3',
          feedback: '继续原题',
          phase: 'repair',
          verdict: 'confirmed_correct',
        },
      ],
      has_more: false,
    })
    const page = mount(TaskHistory, { ...options, props: { task } })
    expect(fake.getData).not.toHaveBeenCalled()
    await page.find('button').trigger('click')
    await flushPromises()
    expect(page.findAll('.event')[0].text()).toContain('11-3')
    expect(page.text()).not.toContain('secret-answer')
    expect(page.text()).toContain('局部订正')
    await page.setProps({ task: { ...task, version: 9, status: 'running' } })
    await flushPromises()
    expect(fake.getData).toHaveBeenCalledTimes(1)
    await page.setProps({ task: { ...task, version: 10, status: 'waiting_student' } })
    await flushPromises()
    expect(fake.getData).toHaveBeenCalledTimes(2)
    page.unmount()
  })
})
