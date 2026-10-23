export function hasUsefulDefinition(value) {
  const text = String(value || '').trim()
  return (
    Boolean(text) &&
    !/是.*(?:中用于解释和解决.*问题的核心知识|核心学习主题，作答时要结合题目条件和本学科证据)[。.]?$/.test(
      text,
    )
  )
}
