import { describe, expect, it } from 'vitest'
import { studyDate } from '../src/utils/learning.js'

describe('诊断日期与复习业务日保持一致', () => {
  it.each([
    ['2026-10-17T15:59:59+00:00', '2026-10-17'],
    ['2026-10-17T16:00:00+00:00', '2026-10-18'],
    ['2026-10-18T00:01:00+08:00', '2026-10-18'],
    ['2025-12-31T16:00:00Z', '2026-01-01'],
    ['2026-02-28T16:00:00Z', '2026-03-01'],
    ['2024-02-28T16:00:00Z', '2024-02-29'],
  ])('%s对应业务日期%s', (input, expected) => {
    expect(studyDate(input)).toBe(expected)
  })
  it('没有日期不补造1970年或今天', () => {
    for (const value of [null, undefined, '']) expect(studyDate(value)).toBe('日期未记录')
  })
  it('无效日期给出核对状态，不导致页面抛错', () => {
    expect(studyDate('not-a-date')).toBe('日期待核对')
  })
})
