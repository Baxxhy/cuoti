export function frameworkGroups(
  nodes,
  { subject = '', grade = '', query = '', weakOnly = false } = {},
) {
  const words = query.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean)
  const groups = new Map()
  for (const node of nodes) {
    if (subject && node.subject !== subject) continue
    if (grade && !String(node.grade || '').includes(grade)) continue
    if (
      weakOnly &&
      !(Number(node.mastery?.evidence_count) > 0 && Number(node.mastery?.mastery_score) < 0.65)
    )
      continue
    const text = [node.name, node.subject, node.grade, node.chapter].join(' ').toLocaleLowerCase()
    if (!words.every((word) => text.includes(word))) continue
    const key = JSON.stringify([node.subject, node.grade, node.chapter])
    if (!groups.has(key))
      groups.set(key, {
        key,
        subject: node.subject,
        grade: node.grade,
        chapter: node.chapter || '基础知识',
        nodes: [],
      })
    groups.get(key).nodes.push(node)
  }
  return [...groups.values()]
}
export function knowledgeProgress(node) {
  if (!(Number(node.mastery?.evidence_count) > 0)) return '尚无作答记录'
  return Number(node.mastery.mastery_score) < 0.65 ? '建议巩固' : '已有学习记录'
}
