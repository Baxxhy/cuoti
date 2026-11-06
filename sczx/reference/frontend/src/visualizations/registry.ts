export const visualizationTypes = [
  'triangle',
  'right_triangle',
  'circle',
  'linear_function',
  'quadratic_function',
  'coordinate_geometry',
  'equation_balance',
  'uniform_motion',
  'uniform_acceleration',
  'projectile_motion',
  'force_diagram',
  'work_energy',
  'pressure',
  'buoyancy',
  'history_timeline',
  'timeline_map',
] as const

export type VisualizationType = (typeof visualizationTypes)[number]
export interface VisualizationSpec {
  schema_version: '1.0'
  type: VisualizationType
  title: string
  teaching_goal: string
  parameters: Record<string, unknown>
  interactive_variables: Array<{
    name: string
    label?: string
    min: number
    max: number
    step?: number
    value: number
  }>
  highlights: unknown[]
  annotations: unknown[]
  student_task: string
  expected_observation: string
}

function validate(value: unknown): VisualizationSpec {
  const item = value as Partial<VisualizationSpec>
  if (
    !item ||
    item.schema_version !== '1.0' ||
    !visualizationTypes.includes(item.type as VisualizationType)
  )
    throw new Error('不支持的互动演示类型')
  for (const key of ['title', 'teaching_goal', 'student_task', 'expected_observation'] as const)
    if (!item[key]) throw new Error(`缺少 ${key}`)
  if (
    !Array.isArray(item.interactive_variables) ||
    !Array.isArray(item.highlights) ||
    !Array.isArray(item.annotations)
  )
    throw new Error('互动演示结构不完整')
  return item as VisualizationSpec
}

export const visualizationSpecSchema = { parse: validate }

export const visualizationLabels: Record<VisualizationType, string> = {
  triangle: '三角形',
  right_triangle: '直角三角形',
  circle: '圆',
  linear_function: '一次函数',
  quadratic_function: '二次函数',
  coordinate_geometry: '坐标几何',
  equation_balance: '等式天平',
  uniform_motion: '匀速运动',
  uniform_acceleration: '匀加速运动',
  projectile_motion: '抛体运动',
  force_diagram: '受力分析',
  work_energy: '功与能',
  pressure: '压强',
  buoyancy: '浮力',
  history_timeline: '历史时间轴',
  timeline_map: '时空关联图',
}

export function parseCatalog(value: unknown): VisualizationSpec[] {
  if (!Array.isArray(value)) throw new Error('互动演示目录必须是数组')
  return value.map(validate)
}
