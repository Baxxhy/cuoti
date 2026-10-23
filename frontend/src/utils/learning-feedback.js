// Readable presentation for historical receipts; original grading evidence stays intact.
export function learningFeedback(value) {
  const text = String(value || '')
  if (
    text === '这次结果还没有核对上，请检查条件和运算后再提交。' ||
    text === '这一步还没有核对上。可以先要一点提示，再重新写一次。'
  )
    return '本次作答不正确，请修改后重试。可以先查看提示，再检查题目条件和你的判断。'
  if (text === '这一步连续几次还没核对上。先要一点提示，或回看原题后再试。')
    return '本次作答不正确。已经连续尝试几次，建议先查看提示，再修改答案。'
  const choice = text.match(/^系统识别到你的选择为[“"]([^”"]*)[”"]，标准答案为[“"]([^”"]*)[”"]。?$/)
  if (choice) return `应选 ${choice[2]}。`
  if (text === '选项与标准答案一致。') return '选对了。'
  if (/^系统识别到最终答案为[“"].*[”"]，与标准答案一致。$/.test(text)) return '答对了。'
  const answer = text.match(
    /^系统识别到的最终答案是[“"]([^”"]*)[”"]，标准答案是[“"]([^”"]*)[”"]。请检查最后一行结论。$/,
  )
  return answer ? `正确答案：${answer[2]}` : text
}
