import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const page = (path: string) => readFileSync(resolve(process.cwd(), `src/${path}`), 'utf8')

describe('学生端教学人格', () => {
  it('统一称呼为小智老师，保留 AI 分析作为功能标题', () => {
    const studentCopy = [page('pages/index/index.vue'), page('pages/tutor/tutor.vue')].join('\n')
    expect(studentCopy).not.toContain('小维老师')
    expect(studentCopy).toContain('小智老师')
    expect(page('pages/diagnosis/diagnosis.vue')).toContain('AI 分析')
  })
})
