export function practiceSize(minutes) {
  return Number(minutes) >= 20 ? 10 : Number(minutes) <= 5 ? 3 : 5
}

export function preferredPracticeUrl(preferences, grade = '') {
  const query = {
    mode: 'practice',
    subject: preferences?.subject || '',
    count: String(practiceSize(preferences?.minutes)),
    minutes: String(preferences?.minutes || 10),
  }
  if (/^初/.test(grade)) query.grade_band = '初中'
  else if (/^高/.test(grade)) query.grade_band = '高中'
  return (
    '/pages/bank/bank?' +
    Object.entries(query)
      .map(([key, value]) => key + '=' + encodeURIComponent(value))
      .join('&')
  )
}
