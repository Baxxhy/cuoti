import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import WrittenAnswer from '../src/components/written-answer/written-answer.vue'
import { uploadFile } from '../src/api/index.js'
vi.mock('../src/api/index.js', () => ({ uploadFile: vi.fn() }))
let pick: any
function setup(props = {}) {
  vi.stubGlobal('uni', {
    chooseImage: vi.fn((options) => {
      pick = options.success
    }),
  })
  return mount(WrittenAnswer, { props: { uploadUrl: '/answers/handwriting', ...props } })
}
afterEach(() => {
  vi.clearAllMocks()
  vi.unstubAllGlobals()
})
describe('照片作答', () => {
  it('恢复已有照片不覆盖文字，忙碌时不能重新选图', async () => {
    const wrapper = setup({ modelValue: '我修改后的答案', disabled: true })
    ;(wrapper.vm as any).restore({
      image_url: '/existing.jpg',
      recognition: { final_answer: 'x=5' },
    })
    await wrapper.vm.$nextTick()
    expect(wrapper.find('image').attributes('src')).toBe('/existing.jpg')
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
    expect(wrapper.find('textarea').attributes('disabled')).toBeDefined()
    await wrapper.find('button').trigger('click')
    expect((globalThis as any).uni.chooseImage).not.toHaveBeenCalled()
    wrapper.unmount()
  })
  it('照片识别失败后保留文字，恢复按钮且不产生未处理异常', async () => {
    const wrapper = setup({ modelValue: '原来的答案' })
    vi.mocked(uploadFile).mockRejectedValueOnce(new Error('503'))
    await wrapper.find('button').trigger('click')
    await expect(pick({ tempFilePaths: ['photo.jpg'] })).resolves.toBeUndefined()
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
    expect(wrapper.text()).toContain('已填写的答案会保留')
    expect(wrapper.emitted('uploading-change')).toEqual([[true], [false]])
    wrapper.unmount()
  })
  it('识别到答案与过程后，最终答案栏不混入过程；移除照片解除关联', async () => {
    const wrapper = setup({ finalAnswerOnly: true, showWorking: true })
    vi.mocked(uploadFile).mockResolvedValueOnce({
      image_url: '/photo.jpg',
      recognition: { final_answer: 'x=5', steps: ['3x=15', 'x=5'], uncertain: false },
    })
    await wrapper.find('button').trigger('click')
    await pick({ tempFilePaths: ['photo.jpg'] })
    expect(wrapper.emitted('update:modelValue')).toEqual([['x=5']])
    expect(wrapper.emitted('update:working')).toEqual([['3x=15\nx=5']])
    await wrapper
      .findAll('button')
      .find((b) => b.text() === '移除')!
      .trigger('click')
    expect(wrapper.emitted('handwriting-change')!.at(-1)).toEqual([
      { image_url: '', recognition: null },
    ])
    wrapper.unmount()
  })
  it('合并过程和答案时不会重复最后一行，保留原始识别证据', async () => {
    const wrapper = setup()
    const recognition = { final_answer: 'x = 5', steps: ['3x=15', 'x=5'] }
    vi.mocked(uploadFile).mockResolvedValueOnce({ image_url: '/photo.jpg', recognition })
    await wrapper.find('button').trigger('click')
    await pick({ tempFilePaths: ['photo.jpg'] })
    expect(wrapper.emitted('update:modelValue')).toEqual([['3x=15\nx=5']])
    expect(wrapper.emitted('handwriting-change')![0]).toEqual([
      { image_url: '/photo.jpg', recognition },
    ])
    wrapper.unmount()
  })
  it('没有识别出文字时明确提示，不覆盖已填写答案', async () => {
    const wrapper = setup({ modelValue: '已有答案' })
    vi.mocked(uploadFile).mockResolvedValueOnce({
      image_url: '/photo.jpg',
      recognition: { final_answer: '', transcription: '', steps: [], uncertain: true },
    })
    await wrapper.find('button').trigger('click')
    await pick({ tempFilePaths: ['photo.jpg'] })
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
    expect(wrapper.text()).toContain('没有识别到可用文字')
    wrapper.unmount()
  })
  it('页面离开后迟到的识别结果不再修改页面或发出答案事件', async () => {
    const wrapper = setup()
    let resolve: any
    vi.mocked(uploadFile).mockImplementationOnce(
      () =>
        new Promise((r) => {
          resolve = r
        }),
    )
    await wrapper.find('button').trigger('click')
    const pending = pick({ tempFilePaths: ['photo.jpg'] })
    wrapper.unmount()
    resolve({ image_url: '/photo.jpg', recognition: { final_answer: 'x=5', steps: [] } })
    await pending
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  })
})
