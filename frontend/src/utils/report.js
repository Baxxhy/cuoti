import { ERROR_TYPE_LABELS } from '@/constants/education.js'

export function reportCauseLabel(value) {
  const raw = String(value || '').trim()
  if (!raw || ['unknown', 'unclassified', 'exact', 'equivalent', 'branch_solution'].includes(raw))
    return ''
  return /^[a-z][a-z0-9_]*$/i.test(raw) ? ERROR_TYPE_LABELS[raw] || '' : raw
}

export function reportGraph(graph) {
  return {
    ...graph,
    nodes: (graph.nodes || []).map((node) => {
      if (node.category !== 'misconception') return node
      const label = reportCauseLabel(node.name)
      return label
        ? { ...node, name: label }
        : {
            ...node,
            name: '待核对的错因',
            detail: '这条学习记录尚未形成明确的错因分类。',
          }
    }),
  }
}

export function reportPointKey(item) {
  return JSON.stringify([item.subject || '', item.knowledge_point || ''])
}

export function reportMastery(items = []) {
  const latest = new Map()
  for (const item of [...items].sort((a, b) =>
    (b.updated_at || '').localeCompare(a.updated_at || ''),
  )) {
    const key = reportPointKey(item)
    if (!latest.has(key)) latest.set(key, item)
  }
  return [...latest.values()]
}

export function reportCauses(items = []) {
  const grouped = new Map()
  for (const item of items) {
    if (item.status === 'resolved') continue
    const raw = String(item.label || item.code || '').trim()
    // Placeholder codes from undiagnosed practice are not established misconceptions.
    const label = reportCauseLabel(raw)
    if (!label) continue
    const key = JSON.stringify([item.subject || '', label])
    const old = grouped.get(key)
    if (!old || item.probability > old.probability)
      grouped.set(key, { ...item, label, search: raw })
  }
  return [...grouped.values()].sort((a, b) => b.probability - a.probability)
}
