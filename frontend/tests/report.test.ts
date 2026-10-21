import { expect, it } from 'vitest'
import { reportCauses, reportGraph, reportMastery } from '../src/utils/report.js'

it('图谱保留未分类历史节点和连线，但不把内部代码展示给学生', () => {
  const source = {
    nodes: [{ id: 'm1', category: 'misconception', name: 'unclassified' }],
    links: [{ source: 'q1', target: 'm1' }],
  }
  const graph = reportGraph(source)
  expect(graph.nodes[0].name).toBe('待核对的错因')
  expect(graph.nodes[0].id).toBe('m1')
  expect(graph.links).toEqual(source.links)
  expect(source.nodes[0].name).toBe('unclassified')
})

it('同名知识按学科保留最新记录，不把旧估计当作当前状态', () => {
  const rows = reportMastery([
    { subject: '数学', knowledge_point: '表达', mastery_score: 0.9, updated_at: '2026-01-01' },
    { subject: '数学', knowledge_point: '表达', mastery_score: 0.3, updated_at: '2026-02-01' },
    { subject: '语文', knowledge_point: '表达', mastery_score: 0.7, updated_at: '2026-02-01' },
  ])
  expect(rows).toHaveLength(2)
  expect(rows.find((row) => row.subject === '数学')?.mastery_score).toBe(0.3)
})

it('已解决和未确认分类不列为主要错因，同名错因不跨学科合并', () => {
  const rows = reportCauses([
    { subject: '数学', label: 'unclassified', probability: 0.99 },
    { subject: '数学', label: 'unknown', probability: 0.99 },
    { subject: '数学', label: '计算错误', status: 'resolved', probability: 0.99 },
    { subject: '数学', label: 'sign_error', probability: 0.4 },
    { subject: '数学', label: '符号错误', probability: 0.6 },
    { subject: '物理', label: '符号错误', probability: 0.5 },
  ])
  expect(rows.map((row) => [row.subject, row.label, row.probability])).toEqual([
    ['数学', '符号错误', 0.6],
    ['物理', '符号错误', 0.5],
  ])
  expect(reportCauses([{ subject: '数学', label: 'sign_error', probability: 0.4 }])[0].search).toBe(
    'sign_error',
  )
})
