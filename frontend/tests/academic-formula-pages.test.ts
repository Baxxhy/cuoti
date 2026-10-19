import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import TeacherQuestions from '../src/pages/teacher/questions.vue'
import TeacherAssignment from '../src/pages/teacher/assignment.vue'
import TeacherReview from '../src/pages/teacher/review-detail.vue'
import Library from '../src/pages/library/library.vue'
import Visualization from '../src/pages/visualization/visualization.vue'
import Tutor from '../src/pages/tutor/tutor.vue'
import StudentReport from '../src/components/student-report/student-report.vue'
import CognitionCanvas from '../src/components/cognition-canvas/cognition-canvas.vue'

const fake = vi.hoisted(() => ({
  getData: vi.fn(),
  postData: vi.fn(),
  hooks: {} as Record<string, (q?: any) => unknown>,
}))
vi.mock('@dcloudio/uni-app', () => ({
  onLoad: (fn: any) => {
    fake.hooks.load = fn
  },
  onShow: (fn: any) => {
    fake.hooks.show = fn
  },
}))
vi.mock('../src/api/index.js', () => ({ getData: fake.getData, postData: fake.postData }))
vi.mock('../src/utils/navigation.js', () => ({ go: vi.fn(), back: vi.fn() }))
const global = {
  stubs: {
    'app-header': true,
    'state-panel': true,
    'uni-icons': true,
    'visualization-canvas': true,
    'written-answer': true,
  },
}
const formula = String.raw`$\frac{1}{5}$`
const root = String.raw`$y=\sqrt{3}x$，点 $A_1$`
const wrappers: ReturnType<typeof mount>[] = []
async function show(component: any, value: any, query: any = {}) {
  fake.getData.mockResolvedValue(value)
  const page = mount(component, { global })
  wrappers.push(page)
  await fake.hooks.load?.(query)
  await fake.hooks.show?.()
  await flushPromises()
  expect(page.find('.math-unparsed').exists()).toBe(false)
  return page
}
beforeEach(() => {
  vi.resetAllMocks()
  fake.hooks = {}
  const canvas = Object.fromEntries(
    [
      'setFillStyle',
      'fillRect',
      'setStrokeStyle',
      'setLineWidth',
      'beginPath',
      'moveTo',
      'lineTo',
      'stroke',
      'draw',
    ].map((k) => [k, vi.fn()]),
  )
  vi.stubGlobal('uni', { createCanvasContext: () => canvas })
})
afterEach(() => {
  wrappers.splice(0).forEach((w) => w.unmount())
  vi.unstubAllGlobals()
})

describe('学科内容跨页面公式渲染', () => {
  it('教师题库同时渲染标题和题干，文字中的HTML不执行', async () => {
    const page = await show(TeacherQuestions, [
      {
        question: {
          id: 'q1',
          title: formula,
          question_text: root + '<img src=x onerror=alert(1)>',
        },
        teacher_question: {},
      },
    ])
    expect(page.find('.row-title .mfrac').exists()).toBe(true)
    expect(page.find('.row-meta .sqrt').exists()).toBe(true)
    expect(page.find('img[onerror]').exists()).toBe(false)
  })
  it('教师布置的题目选择列表渲染公式，选择后保留题目ID并收起', async () => {
    fake.getData.mockImplementation(async (url: string) =>
      url === '/teachers/questions'
        ? [{ question: { id: 'q1', title: '简短标题', question_text: formula } }]
        : [],
    )
    const page = mount(TeacherAssignment, { global })
    wrappers.push(page)
    await fake.hooks.show?.()
    await flushPromises()
    await page.find('.question-picker').trigger('click')
    expect(page.find('.question-options .mfrac').exists()).toBe(true)
    await page.find('.question-options button').trigger('click')
    expect(page.find('.question-options').exists()).toBe(false)
    expect(page.find('.question-picker .mfrac').exists()).toBe(true)
    expect(page.find('.question-picker').attributes('aria-expanded')).toBe('false')
  })
  it('教师复核渲染题干、学生答案和步骤、参考与AI反馈', async () => {
    const page = await show(
      TeacherReview,
      {
        task: { version: 1, ai_result: { feedback: `检查 ${formula}`, evidence: [root] } },
        question: { question_text: root },
        attempt: { answer: formula, steps: [formula] },
        teacher_question: { standard_answer: formula },
        reference_steps: [{ id: 's1', text: formula }],
      },
      { id: 'r1' },
    )
    expect(page.findAll('.mfrac')).toHaveLength(5)
    expect(page.findAll('.sqrt')).toHaveLength(2)
    expect(page.text()).toContain('规则：无')
  })
  it('知识卡名称、正文与相关基础都渲染公式', async () => {
    const page = await show(
      Library,
      {
        code: 'fractions',
        name: formula,
        content: { definition: root },
        prerequisites: [{ code: 'next', name: formula }],
      },
      { code: 'fractions' },
    )
    expect(page.find('h2 .mfrac').exists()).toBe(true)
    expect(page.find('.card-link .mfrac').exists()).toBe(true)
    expect(page.find('.sqrt').exists()).toBe(true)
  })
  it('知识检索结果和章节名称渲染公式', async () => {
    const page = await show(Library, [
      { code: 'fractions', name: formula, content: { chapter: root } },
    ])
    expect(page.find('.knowledge-result .mfrac').exists()).toBe(true)
    expect(page.find('.knowledge-result .sqrt').exists()).toBe(true)
  })
  it('互动演示的题目、标题、教学目标与观察任务都渲染公式', async () => {
    const page = await show(
      Visualization,
      {
        question: { question_text: root },
        spec: {
          type: 'linear_function',
          title: formula,
          teaching_goal: formula,
          student_task: formula,
          expected_observation: formula,
          interactive_variables: [],
        },
      },
      { id: 's1' },
    )
    expect(page.findAll('.mfrac')).toHaveLength(3)
    await page.find('.observation-toggle').trigger('click')
    expect(page.findAll('.mfrac')).toHaveLength(4)
    expect(page.find('.question-context .sqrt').exists()).toBe(true)
  })
  it('教学讲解的答案、解释与历史对话渲染公式', async () => {
    const page = await show(
      Tutor,
      {
        id: 's1',
        stage: 'understanding',
        activity: { type: 'explanation' },
        answer_reveal: {
          topic: formula,
          student_answer: formula,
          correct_answer: formula,
          key_explanation: formula,
          option_explanations: [{ label: 'A', text: root }],
        },
        turns: [{ id: 't1', role: 'assistant', content: formula }],
      },
      { id: 's1' },
    )
    expect(page.findAll('.answer-compare .mfrac')).toHaveLength(2)
    expect(page.find('.why-block .sqrt').exists()).toBe(true)
    await page.find('.history-toggle').trigger('click')
    expect(page.find('.history-turn .mfrac').exists()).toBe(true)
  })
  it('家长报告建议和图谱节点不会展示截断的公式源码', async () => {
    const report = mount(StudentReport, { props: { data: { suggestion: formula } }, global })
    wrappers.push(report)
    expect(report.find('.report-suggestion .mfrac').exists()).toBe(true)
    const graph = mount(CognitionCanvas, {
      props: {
        graph: { nodes: [{ id: 'n1', category: 'knowledge', name: `比较 ${formula}` }], links: [] },
      },
      global,
    })
    wrappers.push(graph)
    await flushPromises()
    expect(graph.find('.node-label .mfrac').exists()).toBe(true)
    expect(graph.find('.math-unparsed').exists()).toBe(false)
    await graph.find('.graph-node').trigger('click')
    expect(graph.emitted('select')![0][0]).toMatchObject({ id: 'n1', name: `比较 ${formula}` })
  })
})
