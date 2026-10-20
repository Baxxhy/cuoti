import { describe, expect, it } from 'vitest'
import { frameworkGroups, knowledgeProgress } from '../src/utils/knowledge-framework.js'
import { insertMathText, mathKeys } from '../src/utils/math-input.js'
describe('长期学习的知识组织', () => {
  const nodes = [
    {
      code: 'a',
      name: '等式的性质',
      subject: '数学',
      grade: '初一',
      chapter: '方程',
      mastery: { mastery_score: 0.4, evidence_count: 2 },
    },
    {
      code: 'b',
      name: '一元二次方程',
      subject: '数学',
      grade: '初三',
      chapter: '方程',
      mastery: null,
    },
    {
      code: 'c',
      name: '语法',
      subject: '英语',
      grade: '初一',
      chapter: '基础',
      mastery: { mastery_score: 0.2, evidence_count: 0 },
    },
  ]
  it('同名章节按学科和年级分开，搜索取交集', () => {
    expect(frameworkGroups(nodes)).toHaveLength(3)
    expect(
      frameworkGroups(nodes, { subject: '数学', query: '初三 方程' })
        .flatMap((x) => x.nodes)
        .map((x) => x.code),
    ).toEqual(['b'])
    expect(
      frameworkGroups(nodes, { grade: '初一', weakOnly: true })
        .flatMap((x) => x.nodes)
        .map((x) => x.code),
    ).toEqual(['a'])
    expect(knowledgeProgress(nodes[2])).toBe('尚无作答记录')
    expect(knowledgeProgress(nodes[0])).toBe('建议巩固')
  })
  it('数学符号在光标处插入，空槽可继续输入且不丢原有文字', () => {
    expect(insertMathText('x=1', mathKeys[0], 2)).toEqual({ value: 'x=\\frac{}{}1', cursor: 8 })
    expect(insertMathText('x', mathKeys[1], null)).toEqual({ value: 'x^{2}', cursor: 5 })
    expect(insertMathText('a'.repeat(1200), mathKeys[0], 3)).toBeNull()
  })
})
