import { ERROR_TYPE_LABELS } from '@/constants/education.js'

export function hasDiagnosisWork(item) {
  return Boolean(
    String(item?.student_answer || '').trim() ||
      (item?.student_steps || []).some((step) =>
        String(step.text || step.formula || step.expression || '').trim(),
      ),
  )
}

export function diagnosisReason(item) {
  const reason = String(item?.diagnosis?.root_misconception || '').trim()
  if (reason && !/无法分析|无法确定|不足以|证据不足|未提供.*作答|没有.*作答/.test(reason))
    return reason
  return '请对照参考答案，检查本次作答是否用全题目条件，以及结论是否符合题意。'
}

function choiceAnswersMatch(item) {
  if (!(item?.options || []).length) return null
  const normalize = (value) => {
    const text = String(value || '')
      .trim()
      .toUpperCase()
    return /^[A-Z](?:[\s、,，]*[A-Z])*$/.test(text)
      ? [...new Set(text.match(/[A-Z]/g))].sort().join('')
      : ''
  }
  const answer = normalize(item.student_answer)
  const reference = normalize(item.analysis?.final_answer)
  return answer && reference ? answer === reference : null
}

// Older saved results treated answer-only work as missing. Reconcile that
// presentation with the actual answer rather than asking for it a second time.
export function diagnosisEvidenceView(item) {
  const value = item?.diagnosis
  if (!value?.evidence_diagnosis || value.user_confirmed || !hasDiagnosisWork(item)) return null
  const evidence = value.evidence_diagnosis
  if (diagnosisView(item).kind === 'clear') return null
  if (evidence.verified) return { ...evidence, title: '步骤核验结果' }
  return {
    ...evidence,
    title: '本次作答分析',
    reason: diagnosisReason(item),
    question: '',
  }
}

export function choiceCorrectionText(item, labels) {
  const options = item?.options || []
  const answer = labels
    .map((label) => {
      const option = options.find(
        (value) => String(value.label || value.key).toUpperCase() === label,
      )
      const text = String(option?.text || option?.content || option?.value || '').trim()
      return text ? `${label}. ${text}` : label
    })
    .join('；')
  const references = (item?.reference_steps || [])
    .map((step) => String(step.text || step.formula || step.expression || step || '').trim())
    .filter(Boolean)
  // Look for the correct option with a label boundary, never the selected
  // wrong option or an English word that happens to contain that letter.
  const reference = references.find((step) =>
    labels.some((label) =>
      new RegExp(
        `(?:选项\\s*|答案(?:为|是|：|:)?\\s*|^\\s*|[^A-Za-z])${label}(?![A-Za-z])`,
        'i',
      ).test(step),
    ),
  )
  const strategy = String(item?.diagnosis?.recommended_strategy || '').trim()
  return [
    `参考答案：${answer}。`,
    reference || strategy || '对照题干逐项核对条件，再独立作答。',
  ].join('\n')
}

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
  const answersMatch = choiceAnswersMatch(item)
  if (
    answersMatch === true ||
    (answersMatch !== false && index == null && ['exact', 'equivalent'].includes(value.error_type))
  )
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
  if (
    hasDiagnosisWork(item) ||
    ((known || step) && (step || String(value.root_misconception || '').trim()))
  )
    return {
      kind: 'finding',
      title: '本次作答的诊断提示',
      message: '结合自己的作答核对，再选择需要复习的知识。',
      step,
    }
  return {
    kind: 'review',
    title: '还没有你的作答',
    message: '先完成这道题，再根据你的答案分析错因。',
    step: null,
  }
}
