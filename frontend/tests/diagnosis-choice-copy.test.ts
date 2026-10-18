import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const source = readFileSync(resolve(process.cwd(), 'src/pages/diagnosis/diagnosis.vue'), 'utf8')

describe('选择题错因诊断文案', () => {
  it('移除多选提示并以选项分析作为标题', () => {
    expect(source).not.toContain('你多选了')
    expect(source).not.toContain('问题出在 {{ focusOptionLabel }}')
    expect(source).toContain('{{ focusOptionLabel }} 选项分析')
  })
})
