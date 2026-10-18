import { ERROR_TYPE_LABELS } from '@/constants/education.js'

export function diagnosisView(item) {
  const value = item?.diagnosis
  if (!value)
    return {
      kind: 'missing',
      title: '先了解本题知识',
      message: '核对题目和作答后，再查看诊断。',
      step: null,
    }
  const index = value.first_error_step
  const step =
    Number.isInteger(index) && index >= 0 && index < (item.student_steps || []).length
      ? index + 1
      : null
  if (index == null && ['exact', 'equivalent'].includes(value.error_type))
    return {
      kind: 'clear',
      title: '当前诊断未发现错误',
      message: '可以回顾本题知识，再独立练一练。',
      step: null,
    }
  const known =
    value.error_type &&
    !['unknown', 'exact', 'equivalent'].includes(value.error_type) &&
    Boolean(ERROR_TYPE_LABELS[value.error_type])
  if ((known || step) && (step || String(value.root_misconception || '').trim()))
    return {
      kind: 'finding',
      title: '本次作答的诊断提示',
      message: '结合自己的作答核对，再选择需要复习的知识。',
      step,
    }
  return {
    kind: 'review',
    title: '诊断还需要核对',
    message: '目前不能定位具体错误，可以补充作答或核对诊断。',
    step: null,
  }
}
