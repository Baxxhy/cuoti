import { visualizationSpecSchema, type VisualizationSpec } from './registry'

export interface TaskVisualization {
  rule_version: 'task-visual-v1'
  source_question_id: string
  source_phase: 'repair' | 'independent' | 'contrast'
  source_equation_tex: string
  current_equation_tex: string
  scope: 'equation_relation' | 'function_expression'
  spec: VisualizationSpec
  values: Record<string, number>
  observation: string
}
function object(value: unknown): Record<string, any> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('图示结构不正确')
  return value as Record<string, any>
}
function keys(value: Record<string, any>, allowed: string[]) {
  if (Object.keys(value).some((key) => !allowed.includes(key)))
    throw new Error('图示包含不支持的字段')
}
function finite(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value) && Math.abs(value) <= 100000000
}
export function parseTaskVisualization(raw: unknown): TaskVisualization {
  const item = object(raw)
  keys(item, [
    'rule_version',
    'source_question_id',
    'source_phase',
    'source_equation_tex',
    'current_equation_tex',
    'scope',
    'spec',
    'values',
    'observation',
  ])
  if (
    item.rule_version !== 'task-visual-v1' ||
    !['repair', 'independent', 'contrast'].includes(item.source_phase)
  )
    throw new Error('图示版本不支持')
  for (const [name, maximum] of [
    ['source_question_id', 36],
    ['source_equation_tex', 1000],
    ['current_equation_tex', 1000],
    ['observation', 1200],
  ] as const) {
    if (
      typeof item[name] !== 'string' ||
      item[name].length > maximum ||
      (name !== 'observation' && !item[name])
    )
      throw new Error('图示文字不完整')
  }
  const spec = object(item.spec)
  keys(spec, [
    'schema_version',
    'type',
    'title',
    'teaching_goal',
    'parameters',
    'interactive_variables',
    'highlights',
    'annotations',
    'student_task',
    'expected_observation',
  ])
  const names =
    spec.type === 'equation_balance'
      ? ['delta']
      : spec.type === 'linear_function'
        ? ['k', 'b']
        : spec.type === 'quadratic_function'
          ? ['a', 'h', 'k']
          : null
  if (
    !names ||
    item.scope !== (spec.type === 'equation_balance' ? 'equation_relation' : 'function_expression')
  )
    throw new Error('图示类型或作用域不匹配')
  visualizationSpecSchema.parse(spec)
  for (const name of ['title', 'teaching_goal', 'student_task', 'expected_observation'])
    if (typeof spec[name] !== 'string' || spec[name].length > 160) throw new Error('图示说明过长')
  if (spec.annotations.length || spec.highlights.length) throw new Error('不支持的图示标注')
  const parameters = object(spec.parameters),
    values = object(item.values)
  const functionNames = [...names, 'center_x', 'center_y', 'x_span', 'y_span']
  keys(
    parameters,
    spec.type === 'equation_balance' ? ['left', 'right', 'task_bound'] : functionNames,
  )
  keys(values, names)
  if (
    Object.keys(values).length !== names.length ||
    spec.interactive_variables.length !== names.length
  )
    throw new Error('图示参数不完整')
  if (spec.type === 'equation_balance') {
    if (
      parameters.task_bound !== true ||
      !finite(parameters.left) ||
      parameters.left !== parameters.right
    )
      throw new Error('等式关系不正确')
  } else if (
    Object.keys(parameters).length !== functionNames.length ||
    parameters.x_span <= 0 ||
    parameters.y_span <= 0 ||
    Object.values(parameters).some((v) => !finite(v))
  )
    throw new Error('函数参数不正确')
  const seen = new Set<string>()
  for (const rawVariable of spec.interactive_variables) {
    const v = object(rawVariable)
    keys(v, ['name', 'label', 'min', 'max', 'step', 'value'])
    if (
      !names.includes(v.name) ||
      seen.has(v.name) ||
      typeof v.label !== 'string' ||
      v.label.length > 40
    )
      throw new Error('图示控件不正确')
    seen.add(v.name)
    if (
      ![v.min, v.max, v.step, v.value, values[v.name]].every(finite) ||
      v.min > v.max ||
      v.step <= 0
    )
      throw new Error('图示数值不正确')
    for (const value of [v.value, values[v.name]])
      if (
        value < v.min ||
        value > v.max ||
        Math.abs((value - v.min) / v.step - Math.round((value - v.min) / v.step)) > 1e-7
      )
        throw new Error('图示数值超出范围')
  }
  return item as TaskVisualization
}
