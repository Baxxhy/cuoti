import { diagnosisView } from './diagnosis.js'
import { reportCauseLabel } from './report.js'

// Pair by persisted IDs only. Different valid solution paths need not have the
// same line count; positional pairing would manufacture a student's mistake.
export function replaySteps(item) {
  const diagnosis = item?.diagnosis
  return (item?.student_steps || []).map((step, index) => {
    const matches = (diagnosis?.evidence || [])
      .map((entry) => ({
        ...entry,
        ...(entry.metadata_json || {}),
      }))
      .filter((entry) => step.id && entry.student_step_id === step.id)
    const references = matches.flatMap((entry) => {
      const reference = (item.reference_steps || []).find(
        (value) => entry.reference_step_id && value.id === entry.reference_step_id,
      )
      return reference ? [{ id: reference.id, text: reference.text, evidence: entry }] : []
    })
    const unique = [...new Map(references.map((entry) => [entry.id, entry])).values()]
    const view = diagnosisView(item)
    const finding = view.kind === 'finding'
    const originalReason = matches
      .map((entry) => entry.reason || entry.explanation)
      .filter(Boolean)
      .join('；')
    return {
      ...step,
      number: index + 1,
      first: finding && diagnosis?.first_error_step === index,
      references: unique,
      evidence: matches,
      aligned: unique.length > 0,
      reason:
        view.kind === 'clear'
          ? '当前诊断未发现错误，可以把参考过程作为另一种思路回顾。'
          : diagnosis?.user_confirmed
            ? diagnosis.first_error_step === index
              ? diagnosis.root_misconception || ''
              : ''
            : originalReason,
    }
  })
}

export function errorGroups(sources = []) {
  const groups = new Map()
  for (const source of sources) {
    const diagnosis = source.diagnosis
    const label = reportCauseLabel(diagnosis?.error_type)
    if (!label || !diagnosis?.root_misconception?.trim()) continue
    const key = JSON.stringify([source.subject, label])
    if (!groups.has(key))
      groups.set(key, { key, label, subject: source.subject, sources: [], points: [] })
    const group = groups.get(key)
    if (group.sources.some((item) => item.id === source.id)) continue
    group.sources.push(source)
    group.points = [...new Set([...group.points, ...(source.knowledge_points || [])])]
  }
  return [...groups.values()]
    .map((group) => ({
      ...group,
      due: group.sources.filter((source) => source.due_review_id).length,
    }))
    .sort(
      (a, b) => b.sources.length - a.sources.length || b.due - a.due || a.key.localeCompare(b.key),
    )
}

export function repairRoute(item, journey) {
  const id = encodeURIComponent(item.id)
  const stages = journey?.stages || []
  const done = (key) => stages.some((stage) => stage.key === key && stage.completed)
  const completed = done
  const progress = journey?.learning_tasks || {}
  const ready = item.confirmed && item.analysis && item.diagnosis
  const next = !ready
    ? 'replay'
    : !completed('understanding') && !progress.original_independent
      ? 'learn'
      : journey?.review?.due
        ? 'review'
        : !completed('transfer')
          ? 'practice'
          : 'review'
  return [
    {
      key: 'knowledge',
      title: '回顾知识',
      detail: item.diagnosis?.missing_prerequisites?.length
        ? `先补：${item.diagnosis.missing_prerequisites.slice(0, 2).join('、')}`
        : '先看概念、条件与方法',
      url: `/pages/knowledge/knowledge?id=${id}`,
      state: '可回看',
    },
    {
      key: 'replay',
      title: '核对作答',
      detail: '对照当时的过程与诊断依据',
      url: `/pages/replay/replay?id=${id}`,
      state: item.diagnosis ? '可核对' : '待诊断',
    },
    {
      key: 'learn',
      title: '订正错题',
      detail: '先订正错处，再重新作答',
      url: '',
      state: completed('understanding')
        ? '已完成理解检查'
        : progress.original_independent
          ? '原题已独立完成'
          : progress.repair_verified
            ? '已订正局部步骤'
            : '待验证',
    },
    {
      key: 'practice',
      title: '类似题练习',
      detail: '同类题与变式题分别练习',
      url: `/pages/practice/practice?id=${id}`,
      state: completed('transfer')
        ? '已完成同类练习'
        : progress.near_transfer
          ? '已完成变式练习'
          : '待验证',
    },
    {
      key: 'review',
      title: '后续复习',
      detail: journey?.review?.next_due_at ? '按已有复习安排继续' : '学习完成后查看复习安排',
      url:
        journey?.review?.due && journey.review.plan_id
          ? `/pages/review/review?plan=${encodeURIComponent(journey.review.plan_id)}`
          : `/pages/journey/journey?id=${id}`,
      state: completed('review') ? '已完成复习' : journey?.review?.due ? '到期复习' : '查看安排',
    },
  ].map((step) => ({ ...step, recommended: step.key === next }))
}
