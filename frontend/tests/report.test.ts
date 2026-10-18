import { expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import StudentReport from '../src/components/student-report/student-report.vue'
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

it('家长报告默认三项知识和三项错因，可展开并在换报告时收起', async () => {
  const data = {
    student: { name: '核验学生' },
    summary: {},
    mastery: Array.from({ length: 5 }, (_, i) => ({
      subject: i === 0 ? '语文' : '数学',
      knowledge_point: `知识${i}`,
      mastery_score: i / 10,
    })),
    misconceptions: Array.from({ length: 5 }, (_, i) => ({
      subject: '数学',
      label: `错因${i}`,
      probability: i / 10,
    })),
  }
  const wrapper = mount(StudentReport, {
    props: { data },
    global: { stubs: { 'math-text': { props: ['text'], template: '<span>{{text}}</span>' } } },
  })
  expect(wrapper.findAll('.mastery')).toHaveLength(3)
  expect(wrapper.findAll('.cause-row')).toHaveLength(3)
  expect(wrapper.text()).toContain('学习记录估计')
  expect(wrapper.text()).toContain('语文')
  await wrapper.findAll('.report-toggle')[0].trigger('click')
  await wrapper.findAll('.report-toggle')[1].trigger('click')
  expect(wrapper.findAll('.mastery')).toHaveLength(5)
  expect(wrapper.findAll('.cause-row')).toHaveLength(5)
  await wrapper.setProps({ data: { ...data, student: { name: '另一位核验学生' } } })
  expect(wrapper.findAll('.mastery')).toHaveLength(3)
  expect(wrapper.findAll('.cause-row')).toHaveLength(3)
  wrapper.unmount()
})

it('已解决和未分类记录可从历史入口查看，不作为主要错因，也不裸露代码', async () => {
  const wrapper = mount(StudentReport, {
    props: {
      data: {
        student: { name: '学生' },
        mastery: [],
        misconceptions: [
          { id: 'one', subject: '数学', label: '计算错误', status: 'resolved' },
          { id: 'two', subject: '物理', label: 'unclassified', status: 'active' },
        ],
      },
    },
    global: { stubs: { 'math-text': { props: ['text'], template: '<span>{{text}}</span>' } } },
  })
  expect(wrapper.findAll('.cause-row')).toHaveLength(0)
  expect(wrapper.text()).not.toContain('计算错误')
  await wrapper.find('.report-toggle').trigger('click')
  expect(wrapper.findAll('.cause-row')).toHaveLength(2)
  expect(wrapper.text()).toContain('已解决记录')
  expect(wrapper.text()).toContain('尚未明确具体错因')
  expect(wrapper.text()).not.toContain('unclassified')
  wrapper.unmount()
})
