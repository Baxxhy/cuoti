import { describe, expect, it } from 'vitest'
import { practiceSize, preferredPracticeUrl } from '../src/utils/study-preferences.js'

describe('学习设置真正控制练习范围和题量', () => {
  it('5/10/20分钟分别生成3/5/10题，并携带学科和学段', () => {
    expect([5, 10, 20].map(practiceSize)).toEqual([3, 5, 10])
    const url = new URL(
      preferredPracticeUrl({ subject: '数学', minutes: 5 }, '初一'),
      'https://local.invalid',
    )
    expect(url.pathname).toBe('/pages/bank/bank')
    expect(Object.fromEntries(url.searchParams)).toEqual({
      mode: 'practice',
      subject: '数学',
      count: '3',
      minutes: '5',
      grade_band: '初中',
    })
    expect(preferredPracticeUrl({ subject: '物理', minutes: 20 }, '高二')).toContain('count=10')
  })
})
