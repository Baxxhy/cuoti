const LOOP_DEFINITIONS = [
  { key: 'questions', label: '错题录入', icon: 'camera-filled' },
  { key: 'diagnoses', label: '错因诊断', icon: 'search' },
  { key: 'sessions', label: '自适应教学', icon: 'chat-filled' },
  { key: 'cognitive_updates', label: '认知更新', icon: 'map-filled' },
  { key: 'pending_reviews', label: '主动复习', icon: 'calendar-filled' },
]

export function buildLearningLoop(metrics = {}) {
  return LOOP_DEFINITIONS.map((item) => ({
    ...item,
    value: Math.max(0, Number(metrics[item.key] || 0)),
  }))
}

export function buildSessionDistribution(metrics = {}) {
  const sessions = Math.max(0, Number(metrics.sessions || 0))
  const active = Math.min(sessions, Math.max(0, Number(metrics.active_sessions || 0)))
  return {
    active,
    completed: sessions - active,
    activePercent: sessions ? Math.round((active / sessions) * 100) : 0,
  }
}
