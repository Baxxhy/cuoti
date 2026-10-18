import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import TaskPage from '../src/pages/task/task.vue'
const fake = vi.hoisted(() => ({
  getData: vi.fn(),
  postData: vi.fn(),
  uploadFile: vi.fn(),
  hooks: {} as Record<string, (...args: any[]) => any>,
  store: { user: { id: 'task-student' }, loadUser: vi.fn() },
}))
vi.mock('@dcloudio/uni-app', () => ({
  onLoad: (fn: any) => (fake.hooks.load = fn),
  onShow: (fn: any) => (fake.hooks.show = fn),
  onHide: (fn: any) => (fake.hooks.hide = fn),
  onUnload: (fn: any) => (fake.hooks.unload = fn),
}))
vi.mock('../src/api/index.js', () => ({
  getData: fake.getData,
  postData: fake.postData,
  uploadFile: fake.uploadFile,
}))
vi.mock('../src/store/index.js', () => ({ useAppStore: () => fake.store }))
vi.mock('../src/utils/navigation.js', () => ({ go: vi.fn(), returnToQuestion: vi.fn() }))
let server: any, storage: Map<string, any>, wrapper: ReturnType<typeof mount> | undefined
const make = async () => {
  wrapper = mount(TaskPage, {
    attachTo: document.body,
    global: {
      stubs: {
        'app-header': true,
        'state-panel': true,
        'task-visualization': {
          name: 'TaskVisualization',
          props: ['packet'],
          emits: ['save', 'close'],
          template: '<div class="mock-visual" />',
        },
        'math-text': { props: ['text'], template: '<span>{{text}}</span>' },
      },
    },
  })
  fake.hooks.load({ id: 't1' })
  fake.hooks.show()
  await flushPromises()
  return wrapper
}
beforeEach(() => {
  vi.useFakeTimers()
  storage = new Map()
  fake.getData.mockReset()
  fake.postData.mockReset()
  fake.uploadFile.mockReset()
  vi.stubGlobal('uni', {
    getStorageSync: (key: string) => storage.get(key),
    setStorageSync: (key: string, value: any) => storage.set(key, structuredClone(value)),
    showModal: vi.fn(),
    chooseImage: vi.fn(),
    previewImage: vi.fn(),
  })
  server = {
    id: 't1',
    question_id: 'q1',
    input_fingerprint: 'fingerprint',
    step_id: 's1',
    version: 2,
    status: 'waiting_student',
    last_request_id: '__initial__',
    student_view: {
      title: '先订正这一步',
      prompt_blocks: [
        { kind: 'question', text: '写出下一行等式' },
        { kind: 'javascript', text: 'should-never-render' },
      ],
      input_kind: 'text',
      secondary_actions: ['hint', 'reveal'],
    },
  }
  fake.getData.mockImplementation(async () => structuredClone(server))
})
afterEach(() => {
  fake.hooks.unload?.()
  wrapper?.unmount()
  document.body.innerHTML = ''
  vi.useRealTimers()
  vi.unstubAllGlobals()
})
describe('持久任务页面', () => {
  it('默认只显示提示和更多方式，展开不提交动作且换步骤后收起', async () => {
    server.student_view.secondary_actions = ['hint', 'visualize', 'reveal']
    const page = await make()
    await page.find('textarea').setValue('还没提交的推导')
    const visibleActions = () =>
      page
        .findAll('.secondary-actions button')
        .filter((b) => b.isVisible())
        .map((b) => b.text())
    expect(visibleActions()).toEqual(['给点提示', '更多方式'])
    expect(page.find('.more-ways').isVisible()).toBe(false)
    await page
      .findAll('.secondary-actions button')
      .find((b) => b.text() === '更多方式')!
      .trigger('keydown', { key: 'Enter' })
    expect(page.find('.more-ways').isVisible()).toBe(true)
    expect(page.find('.more-ways').text()).toContain('拍照或选图作答')
    expect(page.find('.more-ways').text()).toContain('用图看看')
    expect(page.find('.more-ways').text()).toContain('查看参考答案')
    expect(page.find('textarea').element.value).toBe('还没提交的推导')
    expect(fake.postData).not.toHaveBeenCalled()
    expect(fake.uploadFile).not.toHaveBeenCalled()
    server.step_id = 'remote-step'
    server.version++
    fake.hooks.hide()
    fake.hooks.show()
    await flushPromises()
    expect(page.find('.more-ways').isVisible()).toBe(false)
    expect(visibleActions()).toEqual(['给点提示', '更多方式'])
  })
  it('确认看图后才发动作，保存观察使用版本与参数，收起后保留原作答', async () => {
    server.student_view.secondary_actions = ['visualize']
    const page = await make()
    await page.find('textarea').setValue('尚未提交的作答')
    fake.postData.mockImplementation(async (_url, body) => {
      server = {
        ...server,
        version: server.version + 1,
        step_id: `step-${server.version + 1}`,
        last_request_id: body.request_id,
        student_view: {
          ...server.student_view,
          visualization: body.kind === 'close_visualization' ? null : { source_phase: 'repair' },
        },
      }
      return server
    })
    await page
      .findAll('button')
      .find((b) => b.text() === '用图看看')!
      .trigger('click')
    expect(fake.postData).not.toHaveBeenCalled()
    ;(globalThis as any).uni.showModal.mock.calls[0][0].success({ confirm: true })
    await flushPromises()
    expect(fake.postData.mock.calls[0][1]).toMatchObject({
      kind: 'visualize',
      version: 2,
      step_id: 's1',
    })
    expect(page.find('.answer-input').exists()).toBe(false)
    page
      .findComponent({ name: 'TaskVisualization' })
      .vm.$emit('save', { values: { delta: 2 }, text: '等式关系保持' })
    await flushPromises()
    expect(fake.postData.mock.calls[1][1]).toMatchObject({
      kind: 'observe_visualization',
      visual_values: { delta: 2 },
      text: '等式关系保持',
      version: 3,
    })
    page.findComponent({ name: 'TaskVisualization' }).vm.$emit('close')
    await flushPromises()
    expect(page.find('textarea').element.value).toBe('尚未提交的作答')
  })
  it('空转写保留原先文字，明确提示没有识别到内容，不自动提交', async () => {
    const page = await make()
    await page.find('textarea').setValue('原先的文字')
    ;(globalThis as any).uni.chooseImage.mockImplementation(({ success }: any) =>
      success({ tempFilePaths: ['empty-photo.png'] }),
    )
    fake.uploadFile.mockImplementation(async (_url, _file, _name, body) => {
      server = {
        ...server,
        version: 4,
        step_id: 's2',
        last_request_id: body.request_id,
        student_view: {
          ...server.student_view,
          handwriting: { id: 'empty-photo', suggested_text: '', recognition: { uncertain: true } },
        },
      }
      return server
    })
    await page
      .findAll('button')
      .find((b) => b.text() === '拍照或选图作答')!
      .trigger('click')
    await flushPromises()
    expect(page.find('textarea').element.value).toBe('原先的文字')
    expect(page.text()).toContain('没有识别到文字，原先输入已保留')
    expect(fake.postData).not.toHaveBeenCalled()
  })
  it('照片异步受理后核对文字，刷新保留修改，提交只引用服务器照片ID', async () => {
    let page = await make()
    await page.find('textarea').setValue('上传前的文字')
    ;(globalThis as any).uni.chooseImage.mockImplementation(({ success }: any) =>
      success({ tempFilePaths: ['local-photo.png'] }),
    )
    fake.uploadFile.mockImplementation(async (_url, _file, _name, body) => {
      server = {
        ...server,
        current_action: 'recognize_handwriting',
        status: 'running',
        version: 3,
        last_request_id: body.request_id,
      }
      return server
    })
    await page
      .findAll('button')
      .find((b) => b.text() === '拍照或选图作答')!
      .trigger('click')
    await flushPromises()
    expect(fake.uploadFile).toHaveBeenCalledTimes(1)
    expect(fake.postData).not.toHaveBeenCalled()
    expect(page.text()).toContain('正在识别作答照片')
    server = {
      ...server,
      status: 'waiting_student',
      version: 4,
      step_id: 's2',
      student_view: {
        ...server.student_view,
        handwriting: {
          id: 'photo-1',
          suggested_text: 'x=4',
          image_url: '/signed-photo',
          recognition: { uncertain: true },
        },
      },
    }
    await vi.advanceTimersByTimeAsync(1200)
    await flushPromises()
    expect(page.find('textarea').element.value).toBe('x=4')
    expect(page.text()).toContain('部分字迹不清晰')
    expect(page.text()).toContain('恢复上传前的文字')
    await page.find('textarea').setValue('x = 4')
    fake.hooks.unload()
    page.unmount()
    page = await make()
    expect(page.find('textarea').element.value).toBe('x = 4')
    expect(fake.uploadFile).toHaveBeenCalledTimes(1)
    server.student_view.handwriting.image_url = '/refreshed-photo'
    await page
      .findAll('button')
      .find((b) => b.text() === '查看作答照片')!
      .trigger('click')
    await flushPromises()
    expect((globalThis as any).uni.previewImage).toHaveBeenCalledWith({
      urls: ['/refreshed-photo'],
      current: '/refreshed-photo',
    })
    expect(page.find('textarea').element.value).toBe('x = 4')
    fake.postData.mockImplementation(async (_url, body) => {
      server = { ...server, status: 'running', version: 5, last_request_id: body.request_id }
      return server
    })
    await page.find('.primary-btn').trigger('click')
    await flushPromises()
    expect(fake.postData.mock.calls[0][1]).toMatchObject({
      text: 'x = 4',
      handwriting_id: 'photo-1',
      handwriting_confirmed: true,
    })
    expect(fake.postData.mock.calls[0][1]).not.toHaveProperty('handwriting_recognition')
  })
  it('断网后保留回答和请求编号，刷新不会自动重复提交', async () => {
    let page = await make()
    expect(page.text()).not.toContain('should-never-render')
    await page.find('textarea').setValue('2x=8')
    fake.postData.mockRejectedValueOnce(new Error('offline'))
    await page.find('.primary-btn').trigger('click')
    await flushPromises()
    expect(page.find('textarea').element.value).toBe('2x=8')
    await page
      .findAll('button')
      .find((b) => b.text() === '查看参考答案')!
      .trigger('keydown', { key: 'Enter' })
    expect((globalThis as any).uni.showModal).not.toHaveBeenCalled()
    const first = fake.postData.mock.calls[0][1]
    fake.hooks.unload()
    page.unmount()
    page = await make()
    expect(fake.postData).toHaveBeenCalledTimes(1)
    expect(page.find('textarea').element.value).toBe('2x=8')
    fake.postData.mockImplementation(async (_url, body) => {
      server = { ...server, status: 'running', version: 3, last_request_id: body.request_id }
      return server
    })
    await page
      .findAll('button')
      .find((b) => b.text() === '重试刚才的提交')!
      .trigger('click')
    await flushPromises()
    expect(fake.postData.mock.calls[1][1]).toEqual(first)
    server = { ...server, status: 'waiting_student', version: 4, step_id: 's2' }
    await vi.advanceTimersByTimeAsync(1200)
    await flushPromises()
    expect(page.find('textarea').element.value).toBe('')
  })
  it('设备草稿存储已满时仍能提交到后端', async () => {
    const page = await make()
    ;(globalThis as any).uni.setStorageSync = () => {
      throw new Error('quota')
    }
    await page.find('textarea').setValue('2x=8')
    fake.postData.mockImplementation(async (_url, body) => {
      server = { ...server, status: 'running', version: 3, last_request_id: body.request_id }
      return server
    })
    await page.find('.primary-btn').trigger('click')
    await flushPromises()
    expect(fake.postData).toHaveBeenCalledTimes(1)
    expect(fake.postData.mock.calls[0][1].text).toBe('2x=8')
    expect(page.text()).toContain('本机暂时无法保存')
  })
  it('退到后台停止轮询，回到页面读取原任务', async () => {
    server.status = 'running'
    await make()
    const before = fake.getData.mock.calls.length
    fake.hooks.hide()
    await vi.advanceTimersByTimeAsync(5000)
    expect(fake.getData).toHaveBeenCalledTimes(before)
    fake.hooks.show()
    await flushPromises()
    expect(fake.getData).toHaveBeenLastCalledWith('/learning-tasks/t1', { silent: true })
    expect(fake.postData).not.toHaveBeenCalled()
  })
})

it('另一设备推进后隔离旧文字、照片和待提交请求；手动核对后只恢复文字', async () => {
  let page = await make()
  await page.find('textarea').setValue('旧步骤未提交的等式')
  fake.postData.mockRejectedValueOnce(new Error('offline'))
  await page.find('.primary-btn').trigger('click')
  await flushPromises()
  const oldRequest = fake.postData.mock.calls[0][1]
  fake.hooks.unload()
  page.unmount()
  server = {
    ...server,
    version: 8,
    step_id: 'other-device-step',
    last_request_id: 'other-request',
    student_view: { ...server.student_view, title: '换个条件，再试一次' },
  }
  page = await make()
  expect(page.find('textarea').element.value).toBe('')
  expect(page.text()).toContain('旧草稿已单独保留')
  expect(fake.postData).toHaveBeenCalledTimes(1)
  await page
    .findAll('button')
    .find((b) => b.text().startsWith('上一步草稿'))!
    .trigger('click')
  expect(page.text()).toContain('旧步骤未提交的等式')
  await page
    .findAll('button')
    .find((b) => b.text() === '放入当前输入')!
    .trigger('click')
  ;(globalThis as any).uni.showModal.mock.calls.at(-1)[0].success({ confirm: true })
  await flushPromises()
  expect(page.find('textarea').element.value).toBe('旧步骤未提交的等式')
  await page.find('.primary-btn').trigger('click')
  await flushPromises()
  expect(fake.postData.mock.calls[1][1]).toMatchObject({ step_id: 'other-device-step', version: 8 })
  expect(fake.postData.mock.calls[1][1].request_id).not.toBe(oldRequest.request_id)
  expect(fake.postData.mock.calls[1][1]).not.toHaveProperty('handwriting_id')
})

it('达到上限时只提供明确的结束入口，服务端确认后才回原题', async () => {
  const { returnToQuestion } = await import('../src/utils/navigation.js')
  vi.mocked(returnToQuestion).mockClear()
  server = {
    ...server,
    restart_required: true,
    status: 'needs_review',
    student_view: {
      title: '这次学习已到上限',
      input_kind: 'none',
      secondary_actions: [],
      prompt_blocks: [],
    },
  }
  const page = await make()
  expect(page.find('textarea').exists()).toBe(false)
  await page
    .findAll('button')
    .find((b) => b.text() === '结束并回原题')!
    .trigger('click')
  expect(returnToQuestion).not.toHaveBeenCalled()
  fake.postData.mockImplementation(async () => {
    server = { ...server, status: 'cancelled', version: 3 }
    return server
  })
  await (globalThis as any).uni.showModal.mock.calls.at(-1)[0].success({ confirm: true })
  await flushPromises()
  expect(fake.postData).toHaveBeenCalledWith('/learning-tasks/t1/cancel', {})
  expect(returnToQuestion).toHaveBeenCalledWith('q1')
})

it('达到上限后旧输入只读保留，结束后回看本次记录仍可查看', async () => {
  const page = await make()
  await page.find('textarea').setValue('尚未提交的完整解题思路')
  server = {
    ...server,
    restart_required: true,
    step_id: 'remote-limit-step',
    student_view: { ...server.student_view, input_kind: 'none', secondary_actions: [] },
  }
  fake.hooks.show()
  await flushPromises()
  expect(page.find('textarea').exists()).toBe(false)
  await page
    .findAll('button')
    .find((b) => b.text().startsWith('本机未提交草稿'))!
    .trigger('click')
  expect(page.find('.retained-draft').text()).toContain('尚未提交的完整解题思路')
  server = { ...server, status: 'cancelled', restart_required: false }
  fake.hooks.show()
  await flushPromises()
  expect(page.find('.retained-draft').text()).toContain('尚未提交的完整解题思路')
})
