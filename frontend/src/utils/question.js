/** @param {Array<any> | null | undefined} options */
export function normalizeOptions(options = []) {
  return (Array.isArray(options) ? options : []).map((option, index) => {
    const fallback = String.fromCharCode(65 + index)
    if (typeof option === 'string') return { label: fallback, text: option }
    option = option || {}
    return {
      ...option,
      label: String(option.label || option.key || fallback),
      text: String(option.text || option.content || option.value || ''),
    }
  })
}

export function isMultipleChoice(questionType) {
  return /多选|多项|multiple_choice|multiple[-_]response|multi_choice|multi-select/i.test(
    String(questionType || ''),
  )
}

export function questionTypeLabel(questionType) {
  const type = String(questionType || '')
  return (
    {
      'multiple-choice': '单选题',
      choice: '单选题',
      multiple_choice: '多选题',
      'multiple-response': '多选题',
      'fill-in-the-blank': '填空题',
      fill_blank: '填空题',
      calculation: '计算题',
      proof: '证明题',
      subjective: '主观题',
    }[type] ||
    type ||
    '练习题'
  )
}

export function choiceAnswer(values, options) {
  const selected = new Set(values || [])
  return normalizeOptions(options)
    .filter((option) => selected.has(option.label))
    .map((option) => option.label)
    .join('、')
}

export function editedStudentSteps(steps) {
  return steps
    .map((step) => {
      const text = String(step.text || step.formula || step.expression || '').trim()
      return {
        ...step,
        text,
        raw_text: text,
        normalized_text: text.replace(/\s+/g, ' '),
        formula: text.includes('=') ? text : '',
        source: 'user',
      }
    })
    .filter((step) => step.text)
}

export function questionRoute(question) {
  const id = encodeURIComponent(question.id)
  if (question.status === 'awaiting_crop') return `/pages/crop/crop?id=${id}`
  if (['processing', 'pending', 'partial'].includes(question.status) && question.latest_job_id) {
    return `/pages/ocr/ocr?id=${id}&job=${encodeURIComponent(question.latest_job_id)}`
  }
  if (['needs_confirmation', 'ocr_draft', 'processing', 'pending'].includes(question.status))
    return `/pages/ocr/ocr?id=${id}`
  return `/pages/detail/detail?id=${id}`
}
