import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import StudySession from '../src/pages/study-session/study-session.vue'
const fake = vi.hoisted(() => ({ getData: vi.fn(), postData: vi.fn(), load: (_: any) => {} }))
vi.mock('@dcloudio/uni-app', () => ({
  onLoad: (fn: any) => (fake.load = fn),
  onHide: vi.fn(),
  onUnload: vi.fn(),
}))
vi.mock('../src/api/index.js', () => ({
  getData: fake.getData,
  postData: fake.postData,
  patchData: vi.fn(),
}))
vi.mock('../src/utils/navigation.js', () => ({ go: vi.fn() }))
let page: ReturnType<typeof mount> | undefined
beforeEach(() => {
  vi.clearAllMocks()
  vi.stubGlobal('uni', { getStorageSync: vi.fn(), removeStorageSync: vi.fn() })
})
afterEach(() => {
  page?.unmount()
  vi.unstubAllGlobals()
})
for (const mode of ['practice', 'exam']) {
  it(`${mode}每道判错题均显示收录入口，包括配图、选项图和待核验错误；刷新后保持已加入`, async () => {
    const item = (id: string, correct: boolean | null, extra = {}) => ({
      id,
      student_answer: ['C'],
      answer: 'A',
      question: { subject: '物理', question_text: '气体的内能', options: [], image_urls: [] },
      grading: { correct, can_update_learning: true },
      ...extra,
    })
    fake.getData.mockResolvedValue({
      id: 'session',
      user_id: 'student',
      mode,
      status: 'submitted',
      results: { total: 6, max_score: 30, score: 5, correct: 1 },
      items: [
        item('text', false),
        item('image', false, {
          question: {
            question_text: '如图',
            image_urls: ['/image.png'],
            options: [{ label: 'A', text: '', image_urls: ['/a.png'] }],
          },
        }),
        item('uncertain', false, { grading: { correct: false, can_update_learning: false } }),
        item('added', false, { mistake_id: 'saved' }),
        item('right', true),
        item('pending', null),
      ],
    })
    fake.postData.mockResolvedValue({ id: 'saved-new' })
    page = mount(StudySession, {
      global: {
        stubs: {
          'app-header': true,
          'state-panel': true,
          'uni-icons': true,
          'question-content': true,
          'math-text': { props: ['text'], template: '<span>{{text}}</span>' },
        },
      },
    })
    fake.load({ id: 'session' })
    await flushPromises()
    const buttons = page.findAll('.add-mistake')
    expect(buttons).toHaveLength(4)
    expect(buttons[3].text()).toBe('已加入错题本')
    expect(buttons[3].attributes('disabled')).toBeDefined()
    await buttons[1].trigger('click')
    await flushPromises()
    expect(fake.postData).toHaveBeenCalledWith(
      '/questions/manual',
      expect.objectContaining({ study_session_id: 'session', study_item_id: 'image' }),
      { silent: true },
    )
    expect(page.findAll('.add-mistake')[1].text()).toBe('已加入错题本')
  })
}
