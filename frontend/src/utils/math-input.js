export const mathKeys = [
  { label: '分数', text: '\\frac{}{}', offset: 6 },
  { label: '平方', text: '^{2}', offset: 4 },
  { label: '根号', text: '\\sqrt{}', offset: 6 },
  { label: 'π', text: '\\pi ', offset: 4 },
  { label: '±', text: '\\pm ', offset: 4 },
  { label: '≤', text: '\\le ', offset: 4 },
  { label: '≥', text: '\\ge ', offset: 4 },
  { label: '下标', text: '_{}', offset: 2 },
]
export function insertMathText(value, key, cursor, limit = 1200) {
  const text = String(value || '')
  const position = Number.isInteger(cursor)
    ? Math.max(0, Math.min(cursor, text.length))
    : text.length
  if (text.length + key.text.length > limit) return null
  return {
    value: text.slice(0, position) + key.text + text.slice(position),
    cursor: position + key.offset,
  }
}
