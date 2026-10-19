// Readable presentation for historical receipts; original grading evidence stays intact.
export function learningFeedback(value) {
  const text = String(value || '')
  const choice = text.match(/^系统识别到你的选择为[“"]([^”"]*)[”"]，标准答案为[“"]([^”"]*)[”"]。?$/)
  if (choice) return `应选 ${choice[2]}。`
  if (text === '选项与标准答案一致。') return '选对了。'
  if (/^系统识别到最终答案为[“"].*[”"]，与标准答案一致。$/.test(text)) return '答对了。'
  const answer = text.match(
    /^系统识别到的最终答案是[“"]([^”"]*)[”"]，标准答案是[“"]([^”"]*)[”"]。请检查最后一行结论。$/,
  )
  return answer ? `正确答案：${answer[2]}` : text
}
