import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import Knowledge from '../src/pages/knowledge/knowledge.vue'
import Diagnosis from '../src/pages/diagnosis/diagnosis.vue'
import { diagnosisView } from '../src/utils/diagnosis.js'
import { reportCauseLabel } from '../src/utils/report.js'

const fake = vi.hoisted(() => ({
  getData: vi.fn(),
  postData: vi.fn(),
  patchData: vi.fn(),
  go: vi.fn(),
  returnToQuestion: vi.fn(),
  requestLearningTask: vi.fn(),
  hooks: {} as Record<string, (...args: any[]) => any>,
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
  patchData: fake.patchData,
}))
vi.mock('../src/utils/navigation.js', () => ({
  go: fake.go,
  returnToQuestion: fake.returnToQuestion,
}))
vi.mock('../src/utils/task-entry.js', () => ({ requestLearningTask: fake.requestLearningTask }))
let page: ReturnType<typeof mount> | undefined
const stubs = {
  'app-header': true,
  'uni-icons': true,
  'state-panel': true,
  'math-text': { props: ['text'], template: '<span>{{text}}</span>' },
}
function make(component: any = Knowledge) {
  page = mount(component, { global: { stubs } })
  fake.hooks.load({ id: 'question-1' })
  fake.hooks.show()
  return page
}
const base = {
  id: 'question-1',
  subject: '数学',
  grade: '初三',
  confirmed: true,
  question_type: '计算题',
  student_answer: 'x=2',
  student_steps: [{ text: 'x=2' }],
  analysis: {
    knowledge_points: ['一元二次方程'],
    prerequisites: ['因式分解'],
    reference_steps: ['x=2 或 x=3'],
  },
}
beforeEach(() => {
  vi.clearAllMocks()
  fake.requestLearningTask.mockReset().mockResolvedValue({ id: 'shared-task' })
  fake.hooks = {}
})

it('非规则证明的诊断修复明确显示待核对，不显示确定正确的标题', async () => {
  fake.getData.mockResolvedValue({
    ...base,
    knowledge_points: ['速度单位换算关系：$1\\text{ m/s}=3.6\\text{ km/h}$'],
    diagnosis: {
      first_error_step: 0,
      error_type: 'unit_error',
      root_misconception: '请检查原题是否给出此条件。',
      recommended_strategy: '根据原题核对已知条件。',
      counterfactual: {
        verification_method: 'qwen_proposal_requires_review',
        root_cause_confirmed: false,
      },
      evidence: [
        { student_step_id: 's0', verification_scope: 'model_review_requires_confirmation' },
      ],
    },
  })
  const view = make(Diagnosis)
  await flushPromises()
  expect(view.text()).toContain('参考修正（待核对）')
  expect(view.text()).toContain('尚未经本地规则验证')
  expect(view.text()).toContain('根据原题核对已知条件。')
  expect(view.find('.summary-title').text()).toContain('单位错误')
  expect(view.find('.summary-title').text()).not.toContain('\\text')
})

it('诊断默认进入持久任务，失败留在原页并允许重试', async () => {
  fake.getData.mockResolvedValue({
    ...base,
    diagnosis: {
      first_error_step: 0,
      error_type: 'condition_omission',
      root_misconception: '还缺少另一个解。',
      counterfactual: {},
    },
  })
  fake.requestLearningTask.mockRejectedValueOnce(new Error('连接中断，请重试'))
  const view = make(Diagnosis)
  await flushPromises()
  await view.find('.tutor-btn').trigger('click')
  await flushPromises()
  expect(view.find('[role="alert"]').text()).toContain('连接中断')
  expect(fake.go).not.toHaveBeenCalled()
  await view.find('.tutor-btn').trigger('click')
  await flushPromises()
  expect(fake.requestLearningTask).toHaveBeenLastCalledWith('question-1')
  expect(fake.go).toHaveBeenCalledWith('/pages/task/task?id=shared-task')
  expect(fake.postData).not.toHaveBeenCalled()
})

it('未发现错误时可直接继续学习，知识与参考过程仍可查看', async () => {
  fake.getData.mockResolvedValue({
    ...base,
    diagnosis: { error_type: 'exact', first_error_step: null, counterfactual: {} },
  })
  const view = make(Diagnosis)
  await flushPromises()
  expect(view.find('.tutor-btn').text()).toBe('继续学习')
  expect(view.text()).toContain('查看本题知识')
  expect(view.text()).toContain('查看参考过程')
  await view.find('.tutor-btn').trigger('click')
  await flushPromises()
  expect(fake.go).toHaveBeenCalledWith('/pages/task/task?id=shared-task')
})

it('离开后返回的旧创建回执不会突然跳页', async () => {
  fake.getData.mockResolvedValue({
    ...base,
    diagnosis: { error_type: 'exact', first_error_step: null, counterfactual: {} },
  })
  let finish: (value: any) => void = () => {}
  fake.requestLearningTask.mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve
      }),
  )
  const view = make(Diagnosis)
  await flushPromises()
  await view.find('.tutor-btn').trigger('click')
  fake.hooks.hide()
  fake.hooks.show()
  await flushPromises()
  finish({ id: 'late-task' })
  await flushPromises()
  expect(fake.go).not.toHaveBeenCalled()
  expect(view.text()).toContain('当前诊断未发现错误')
})

it('诊断返回重读，隐藏前的旧题响应不覆盖新结果', async () => {
  let finish: (value: any) => void = () => {}
  fake.getData.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finish = resolve
      }),
  )
  const view = make(Diagnosis)
  fake.hooks.hide()
  fake.getData.mockResolvedValueOnce({
    ...base,
    diagnosis: {
      first_error_step: 0,
      error_type: 'condition_omission',
      root_misconception: '新的核对结果',
      counterfactual: {},
    },
  })
  fake.hooks.show()
  await flushPromises()
  finish({
    ...base,
    diagnosis: { error_type: 'exact', first_error_step: null, counterfactual: {} },
  })
  await flushPromises()
  expect(view.text()).toContain('新的核对结果')
  expect(view.text()).not.toContain('当前诊断未发现错误')
})
afterEach(() => page?.unmount())

it('未诊断和待核对记录不会被称为已经确定的错因', () => {
  expect(diagnosisView(base).kind).toBe('missing')
  expect(
    diagnosisView({ ...base, diagnosis: { error_type: 'unknown', first_error_step: null } }).kind,
  ).toBe('review')
  expect(
    diagnosisView({
      ...base,
      diagnosis: {
        error_type: 'calculation_error',
        first_error_step: 99,
        root_misconception: '需要核对',
      },
    }).step,
  ).toBeNull()
  for (const code of ['exact', 'equivalent', 'branch_solution'])
    expect(reportCauseLabel(code)).toBe('')
})

it('未发现错误的知识页不指责学生，返回原题而不创建重复教学会话', async () => {
  fake.getData.mockResolvedValue({
    ...base,
    diagnosis: { error_type: 'exact', first_error_step: null },
  })
  const view = make()
  await flushPromises()
  expect(view.text()).toContain('当前诊断未发现错误')
  expect(view.text()).not.toContain('需要重新理解')
  expect(view.text()).not.toContain('出现问题')
  await view.find('.primary-btn').trigger('click')
  expect(fake.returnToQuestion).toHaveBeenCalledWith('question-1')
  expect(fake.postData).not.toHaveBeenCalled()
})

it('长知识列表和完整作答按需打开，公式不被盲目截断', async () => {
  const work = '$' + 'x+1+'.repeat(30) + 'x=2$'
  fake.getData.mockResolvedValue({
    ...base,
    analysis: {
      ...base.analysis,
      knowledge_points: ['一元二次方程', '因式分解', '零乘积性质', '求根公式'],
    },
    diagnosis: {
      error_type: 'condition_omission',
      first_error_step: 0,
      first_error_text: work,
      root_misconception: '还需要核对另一个分支。',
    },
  })
  const view = make()
  await flushPromises()
  expect(view.text()).not.toContain('求根公式')
  await view.find('.knowledge-card .expand-btn').trigger('click')
  expect(view.text()).toContain('求根公式')
  expect(view.text()).not.toContain(work)
  await view.find('.diagnosis-card .expand-btn').trigger('click')
  expect(view.find('.work-quote').text()).toContain(work)
})

it('返回知识页会重读诊断，离开后的迟到响应不能恢复旧数据', async () => {
  let resolve: (value: any) => void = () => {}
  fake.getData.mockReturnValueOnce(
    new Promise((done) => {
      resolve = done
    }),
  )
  const view = make()
  fake.hooks.hide()
  resolve(base)
  await flushPromises()
  expect(view.text()).not.toContain('一元二次方程')
  fake.getData.mockResolvedValueOnce({ ...base, analysis: { knowledge_points: ['新的知识点'] } })
  fake.hooks.show()
  await flushPromises()
  expect(view.text()).toContain('新的知识点')
  expect(fake.getData).toHaveBeenCalledTimes(2)
})

it('诊断没有具体错误时不虚构第1步，仍可打开人工修正', async () => {
  fake.getData.mockResolvedValue({
    ...base,
    diagnosis: { error_type: 'exact', first_error_step: null },
  })
  const view = make(Diagnosis)
  await flushPromises()
  expect(view.text()).toContain('当前诊断未发现错误')
  expect(view.text()).not.toContain('你错在这里')
  expect(view.text()).not.toContain('第 1 步')
  await view.find('.feedback-link').trigger('click')
  expect(view.find('.correction-card').exists()).toBe(true)
})

it('正确判断优先使用已验证修复，不把校验用的原方程冒充修复步骤', async () => {
  fake.getData.mockResolvedValue({
    ...base,
    diagnosis: {
      error_type: 'condition_omission',
      first_error_step: 0,
      first_error_text: 'x=2',
      root_misconception: '需要补全另一个解。',
      evidence: [
        {
          is_first_error: true,
          metadata_json: { reference_text: 'x**2-5*x+6=0', verification_scope: 'branch_root' },
        },
      ],
      counterfactual: { root_cause_confirmed: true, corrected_step: 'x=2 或 x=3' },
    },
  })
  const view = make(Diagnosis)
  await flushPromises()
  expect(view.find('.correct-thought').text()).toContain('x=2 或 x=3')
  expect(view.find('.correct-thought').text()).not.toContain('x**2')
})

it('人工修正使用从1开始的步骤，保存失败保留输入，越界不提交', async () => {
  fake.getData.mockResolvedValue({
    ...base,
    diagnosis: {
      first_error_step: 0,
      error_type: 'sign_error',
      root_misconception: '原说明',
      counterfactual: {},
    },
  })
  const view = make(Diagnosis)
  await flushPromises()
  await view.find('.feedback-link').trigger('click')
  const field = view.find('.correction-card input')
  expect((field.element as HTMLInputElement).value).toBe('1')
  await field.setValue('2')
  await view.find('.correction-card .primary-btn').trigger('click')
  expect(fake.patchData).not.toHaveBeenCalled()
  expect(view.find('.correction-card [role="alert"]').text()).toContain('实际作答')
  await field.setValue('1')
  fake.patchData.mockRejectedValueOnce(new Error('连接中断'))
  await view.find('.correction-card .primary-btn').trigger('click')
  await flushPromises()
  expect(fake.patchData).toHaveBeenLastCalledWith(
    '/questions/question-1/diagnosis',
    expect.objectContaining({ first_error_step: 0 }),
  )
  expect(view.find('.correction-card [role="alert"]').text()).toContain('连接中断')
  expect((field.element as HTMLInputElement).value).toBe('1')
  fake.patchData.mockResolvedValueOnce({})
  await view.find('.correction-card .primary-btn').trigger('click')
  await flushPromises()
  expect(view.find('.correction-card').exists()).toBe(false)
})

it('未定位的人工修正留空，不凭空选择第一步', async () => {
  fake.getData.mockResolvedValue({
    ...base,
    diagnosis: {
      first_error_step: null,
      error_type: 'unknown',
      root_misconception: '',
      counterfactual: {},
    },
  })
  const view = make(Diagnosis)
  await flushPromises()
  await view.find('.feedback-link').trigger('click')
  expect((view.find('.correction-card input').element as HTMLInputElement).value).toBe('')
  fake.patchData.mockResolvedValueOnce({})
  await view.find('.correction-card .primary-btn').trigger('click')
  await flushPromises()
  expect(fake.patchData).toHaveBeenLastCalledWith(
    '/questions/question-1/diagnosis',
    expect.objectContaining({ first_error_step: null }),
  )
})

it('参考一致的建议不冒充规则验证，保留学生核对提示', async () => {
  fake.getData.mockResolvedValue({
    ...base,
    diagnosis: {
      first_error_step: 0,
      error_type: 'formula_error',
      root_misconception: '核对公式',
      counterfactual: {
        reference_consistent: true,
        preserved_prefix: true,
        root_cause_confirmed: false,
      },
    },
  })
  const view = make(Diagnosis)
  await flushPromises()
  expect(view.find('.evidence-caption[role="status"]').text()).toContain('仍需结合原题核对')
})

it('历史验证标签和改动正确前缀的修复都明确需要核对', async () => {
  fake.getData.mockResolvedValue({
    ...base,
    diagnosis: {
      first_error_step: 0,
      error_type: 'calculation_error',
      counterfactual: { legacy_review_required: true, root_cause_confirmed: false },
    },
  })
  const view = make(Diagnosis)
  await flushPromises()
  expect(view.find('.evidence-caption[role="status"]').text()).toContain('历史修复建议')
  fake.getData.mockResolvedValue({
    ...base,
    diagnosis: {
      first_error_step: 0,
      error_type: 'calculation_error',
      counterfactual: { preserved_prefix: false, root_cause_confirmed: false },
    },
  })
  fake.hooks.show()
  await flushPromises()
  expect(view.find('.evidence-caption[role="status"]').text()).toContain('改动了前面正确的步骤')
})

it('人工改到第二步后，按该步ID取参考，不沿用旧首错标记', async () => {
  fake.getData.mockResolvedValue({
    ...base,
    student_steps: [
      { id: 's0', text: '2x=14' },
      { id: 's1', text: 'x=7' },
    ],
    reference_steps: [
      { id: 'r0', text: '2x=8' },
      { id: 'r1', text: 'x=4' },
    ],
    diagnosis: {
      first_error_step: 1,
      error_type: 'calculation_error',
      user_confirmed: true,
      first_error_text: 'x=7',
      root_misconception: '核对第二步',
      counterfactual: { root_cause_confirmed: false, stale_after_correction: true },
      evidence: [
        {
          student_step_id: 's0',
          reference_step_id: 'r0',
          is_first_error: true,
          reference_text: '2x=8',
        },
        { student_step_id: 's1', reference_step_id: 'r1', reference_text: 'x=4' },
      ],
    },
  })
  const view = make(Diagnosis)
  await flushPromises()
  expect(view.find('.correct-thought').text()).toContain('x=4')
  expect(view.find('.correct-thought').text()).not.toContain('2x=8')
  expect(view.find('.evidence-caption[role="status"]').text()).toContain('原有修复建议需要重新核对')
})

it('人工改到没有ID对应证据的步骤时，不拿相同行号参考补造对应', async () => {
  fake.getData.mockResolvedValue({
    ...base,
    student_steps: [
      { id: 's0', text: '2x=14' },
      { id: 's1', text: 'x=7' },
    ],
    reference_steps: [
      { id: 'r0', text: '2x=8' },
      { id: 'r1', text: '行号相同但未核实的参考' },
    ],
    diagnosis: {
      first_error_step: 1,
      error_type: 'calculation_error',
      user_confirmed: true,
      first_error_text: 'x=7',
      root_misconception: '核对第二步',
      recommended_strategy: '旧建议：第一步应该移项减3',
      counterfactual: {},
      evidence: [{ student_step_id: 's0', is_first_error: true, reference_text: '旧首错参考' }],
    },
  })
  const view = make(Diagnosis)
  await flushPromises()
  expect(view.find('.correct-thought').text()).toContain('暂无与你标记步骤对应的参考')
  expect(view.find('.correct-thought').text()).not.toContain('旧建议')
  expect(view.findAll('.section-title').map((node) => node.text())).toContain('这一步还需核对')
  expect(view.findAll('.section-title').map((node) => node.text())).toContain('当前诊断说明')
  expect(view.find('.correct-thought').text()).not.toContain('旧首错参考')
  expect(view.find('.correct-thought').text()).not.toContain('行号相同但未核实的参考')
})

it('人工修正仍有本步有效修复证明时，保留已验证的具体做法', async () => {
  fake.getData.mockResolvedValue({
    ...base,
    student_steps: [
      { id: 's0', text: '2x=14' },
      { id: 's1', text: 'x=7' },
    ],
    diagnosis: {
      first_error_step: 1,
      error_type: 'calculation_error',
      user_confirmed: true,
      first_error_text: 'x=7',
      root_misconception: '本步应除以2',
      counterfactual: {
        root_cause_confirmed: true,
        suspected_step: 1,
        corrected_step: 'x=4',
        validation_scope: 'polynomial_real_solution_set_and_preserved_prefix',
      },
      evidence: [],
    },
  })
  const view = make(Diagnosis)
  await flushPromises()
  expect(view.find('.correct-thought').text()).toContain('x=4')
  expect(view.findAll('.section-title').map((node) => node.text())).toContain('这一步应该怎么改')
  expect(view.text()).not.toContain('暂无与你标记步骤对应的参考')
})
