import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import TaskVisualization from '../src/components/task-visualization/task-visualization.vue'
import { parseTaskVisualization } from '../src/visualizations/task-visualization'

vi.mock('../src/store/index.js', () => ({
  useAppStore: () => ({ user: { id: 'visual-student' } }),
}))
const packet = () => ({
  rule_version: 'task-visual-v1',
  source_question_id: 'q1',
  source_phase: 'repair',
  source_equation_tex: '2x+3=11',
  current_equation_tex: '2x+3=11',
  scope: 'equation_relation',
  values: { delta: 0 },
  observation: '',
  spec: {
    schema_version: '1.0',
    type: 'equation_balance',
    title: '等式两边同操作',
    teaching_goal: '观察等式关系',
    parameters: { left: 11, right: 11, task_bound: true },
    interactive_variables: [
      { name: 'delta', label: '两边同时减去', min: -5, max: 5, step: 1, value: 0 },
    ],
    highlights: [],
    annotations: [],
    student_task: '观察两边',
    expected_observation: '同操作',
  },
})
const options = {
  global: {
    stubs: {
      'visualization-canvas': true,
      'math-text': { props: ['text'], template: '<span>{{text}}</span>' },
    },
  },
}
const props = () => ({
  packet: packet(),
  taskId: 't1',
  fingerprint: 'fp-1',
  stepId: 's1',
  busy: false,
})
beforeEach(() => {
  const values = new Map()
  vi.stubGlobal('uni', {
    getStorageSync: (key: string) => values.get(key),
    setStorageSync: (key: string, value: any) => values.set(key, structuredClone(value)),
  })
})
describe('来源图示合同与观察', () => {
  it('拒绝非白名单字段、参数、类型和不正确范围', () => {
    expect(parseTaskVisualization(packet()).spec.type).toBe('equation_balance')
    for (const change of [
      { ...packet(), code: 'alert(1)' },
      { ...packet(), values: { delta: true } },
      { ...packet(), values: { delta: 0.5 } },
      { ...packet(), values: { delta: Infinity } },
      { ...packet(), values: { other: 1 } },
      { ...packet(), spec: { ...packet().spec, type: 'model_javascript' } },
      {
        ...packet(),
        spec: { ...packet().spec, parameters: { ...packet().spec.parameters, javascript: 'x' } },
      },
    ])
      expect(() => parseTaskVisualization(change)).toThrow()
  })
  it('按钮可调参数；关闭和刷新保留未提交观察，保存只发观察而不宣称正确', async () => {
    let page = mount(TaskVisualization, { ...options, props: props() })
    await page.find('[aria-label="增大两边同时减去"]').trigger('keydown', { key: 'Enter' })
    await page.find('textarea').setValue('我发现两边要做相同运算')
    expect(page.text()).toContain('等式两边同时减去1')
    await page
      .findAll('button')
      .find((b) => b.text() === '收起图示')!
      .trigger('click')
    expect(page.emitted('close')).toHaveLength(1)
    page.unmount()
    page = mount(TaskVisualization, { ...options, props: props() })
    expect(page.find('textarea').element.value).toBe('我发现两边要做相同运算')
    expect(page.text()).toContain('等式两边同时减去1')
    await page
      .findAll('button')
      .find((b) => b.text() === '保存观察')!
      .trigger('click')
    expect(page.emitted('save')![0][0]).toEqual({
      values: { delta: 1 },
      text: '我发现两边要做相同运算',
    })
    expect(page.text()).not.toContain('已保存这次观察')
    await page.setProps({ busy: true })
    await page.find('[aria-label="增大两边同时减去"]').trigger('keydown', { key: 'Enter' })
    expect(page.text()).toContain('等式两边同时减去1')
    page.unmount()
  })
  it('别处已保存新记录时保留草稿，主动选择后才用服务器记录替换', async () => {
    let page = mount(TaskVisualization, { ...options, props: props() })
    await page.find('textarea').setValue('还没保存的观察')
    page.unmount()
    const saved = { ...packet(), values: { delta: 2 }, observation: '另一个窗口保存的观察' }
    page = mount(TaskVisualization, { ...options, props: { ...props(), packet: saved } })
    await flushPromises()
    expect(page.text()).toContain('图示记录已有更新')
    expect(page.find('textarea').element.value).toBe('还没保存的观察')
    expect(page.text()).toContain('另一个窗口保存的观察')
    await page
      .findAll('button')
      .find((b) => b.text() === '使用已保存的记录')!
      .trigger('click')
    expect(page.find('textarea').element.value).toBe('另一个窗口保存的观察')
    expect(page.text()).toContain('已保存这次观察')
    page.unmount()
  })
})

it('分数初值按网格调整，函数原式视窗和常函数边界保持可读', async () => {
  const raw: any = packet()
  raw.source_phase = 'independent'
  raw.source_equation_tex = raw.current_equation_tex = 'y=x/3+1000'
  raw.scope = 'function_expression'
  raw.values = { k: 1 / 3, b: 1000 }
  raw.spec.type = 'linear_function'
  raw.spec.parameters = { k: 1 / 3, b: 1000, center_x: 0, center_y: 1000, x_span: 6, y_span: 6 }
  raw.spec.interactive_variables = [
    { name: 'k', label: '斜率 k', min: 1 / 3 - 2.5, max: 1 / 3 + 2.5, step: 0.5, value: 1 / 3 },
    { name: 'b', label: '截距 b', min: 998.75, max: 1001.25, step: 0.25, value: 1000 },
  ]
  expect(parseTaskVisualization(raw).spec.parameters.center_y).toBe(1000)
  const page = mount(TaskVisualization, { ...options, props: { ...props(), packet: raw } })
  await page.find('[aria-label="增大斜率 k"]').trigger('click')
  await page.find('textarea').setValue('斜率增大了')
  await page
    .findAll('button')
    .find((b) => b.text() === '保存观察')!
    .trigger('click')
  const changed = page.emitted('save')![0][0] as any
  expect(() => parseTaskVisualization({ ...raw, values: changed.values })).not.toThrow()
  expect(changed.values.k).toBeCloseTo(5 / 6, 12)
  expect(page.text()).toContain('约')
  expect(() =>
    parseTaskVisualization({
      ...raw,
      spec: { ...raw.spec, parameters: { ...raw.spec.parameters, x_span: 0 } },
    }),
  ).toThrow()
  page.unmount()
})

it('步骤改变但保存内容未变时也拦截旧观察，核对后才能保存', async () => {
  let page = mount(TaskVisualization, { ...options, props: { ...props(), stepId: 's1' } })
  await page.find('textarea').setValue('还未提交的旧步骤观察')
  page.unmount()
  page = mount(TaskVisualization, { ...options, props: { ...props(), stepId: 'remote-s2' } })
  await flushPromises()
  expect(page.text()).toContain('图示记录已有更新')
  const save = page.findAll('button').find((b) => b.text() === '保存观察')!
  expect(save.attributes('disabled')).toBeDefined()
  await save.trigger('click')
  expect(page.emitted('save')).toBeUndefined()
  await page
    .findAll('button')
    .find((b) => b.text() === '核对后使用草稿')!
    .trigger('click')
  await save.trigger('click')
  expect(page.emitted('save')).toHaveLength(1)
  page.unmount()
})
