import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import {
  CORE_SUBJECTS,
  ERROR_TYPE_LABELS,
  MIDDLE_SCHOOL_GRADES,
  errorTypeLabel,
} from '../src/constants/education.js'

describe('中学课程与学生文案', () => {
  it('覆盖初一至高三和中学核心学科', () => {
    expect(MIDDLE_SCHOOL_GRADES).toEqual(['初一', '初二', '初三', '高一', '高二', '高三'])
    expect(CORE_SUBJECTS).toContain('语文')
    expect(CORE_SUBJECTS).toContain('英语')
    expect(CORE_SUBJECTS).toContain('化学')
    expect(CORE_SUBJECTS).toContain('生物')
    expect(CORE_SUBJECTS).toContain('地理')
    expect(CORE_SUBJECTS.length).toBe(10)
  })

  it('所有内部错因代码都有中文显示，未知代码不直接泄露', () => {
    expect(ERROR_TYPE_LABELS.causality_confusion).toBe('历史因果混淆')
    expect(ERROR_TYPE_LABELS.unit_error).toBe('单位错误')
    expect(errorTypeLabel('unmapped_internal_code')).toBe('需要进一步确认')
  })

  it('复习页要求先作答和判定，再允许自评', () => {
    const source = readFileSync(resolve(process.cwd(), 'src/pages/review/review.vue'), 'utf8')
    expect(source).toContain('/attempt')
    expect(source).toContain('提交并判定')
    expect(source).toContain('attempt_id')
    expect(source.indexOf('提交并判定')).toBeLessThan(source.indexOf('还不会'))
  })
})
