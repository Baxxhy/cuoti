import { afterEach, describe, expect, it, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import {
  filterQuestions,
  groupQuestions,
  dueToday,
  questionStatus,
  paperURL,
  questionSearchURL,
  saveNotebookView,
  notebookView,
  clearNotebookViews,
} from '../src/utils/learning.js'
import { switchSection } from '../src/utils/navigation.js'
import { learningSections } from '../src/constants/learning.js'
const now = new Date('2026-10-16T12:00:00Z')
const questions = [
  {
    id: 'a',
    subject: '数学',
    grade: '初一',
    confirmed: false,
    favorite: true,
    knowledge_points: ['方程'],
    mastery_score: 1,
  },
  {
    id: 'b',
    subject: '数学',
    grade: '初一',
    confirmed: true,
    favorite: true,
    diagnosis_summary: '漏看条件',
    review_due_at: '2026-10-16T15:59:00Z',
    knowledge_points: ['方程'],
  },
  {
    id: 'c',
    subject: '数学',
    grade: '高一',
    confirmed: true,
    diagnosis_summary: '漏看条件',
    review_due_at: '2026-10-16T16:00:00Z',
    knowledge_points: ['方程'],
  },
  {
    id: 'd',
    subject: '物理',
    grade: '初一',
    confirmed: true,
    diagnosis_summary: '等待完成错因诊断',
  },
]
afterEach(() => {
  vi.unstubAllGlobals()
  clearNotebookViews()
})
describe('学习功能边界', () => {
  it('组合筛选取交集，分数再高也不能跳过确认', () => {
    expect(
      filterQuestions(
        questions,
        { subject: '数学', favorite: true, due: true, stage: 'learn' },
        now,
      ).map((x) => x.id),
    ).toEqual(['b'])
    expect(filterQuestions(questions, { stage: 'confirm' }).map((x) => x.id)).toEqual(['a'])
    expect(filterQuestions(questions, { stage: 'diagnose' }).map((x) => x.id)).toEqual(['d'])
    expect(questionStatus(questions[0])).toBe('待核对')
    expect(questionStatus(questions[1])).not.toContain('掌握')
  })
  it('到期按上海日期判断，不把明天或无效时间计入今天', () => {
    expect(dueToday(questions[1].review_due_at, now)).toBe(true)
    expect(dueToday(questions[2].review_due_at, now)).toBe(false)
    expect(dueToday('invalid', now)).toBe(false)
    expect(dueToday(null, now)).toBe(false)
  })
  it('按标签整理不跨年级合并，也不修改题目证据', () => {
    const copy = JSON.stringify(questions)
    const groups = groupQuestions(questions, 'cause')
    expect(groups.filter((x) => x.title === '漏看条件')).toHaveLength(2)
    expect(groupQuestions(questions, 'knowledge')).toHaveLength(3)
    expect(JSON.stringify(questions)).toBe(copy)
  })
  it('检索和组卷正确编码特殊字符，保持题目范围', () => {
    expect(questionSearchURL({ subject: '数学', search: 'a+b&c' })).toContain('a%2Bb%26c')
    const url = new URL(paperURL({ subject: '数学', ids: ['q1', 'q2'] }), 'https://local.test')
    expect(url.searchParams.get('ids')).toBe('q1,q2')
    expect(url.searchParams.get('subject')).toBe('数学')
  })
  it('界面筛选按用户隔离并在退出时清除', () => {
    saveNotebookView('user-a', { subject: '数学' })
    expect(notebookView('user-b')).toEqual({})
    expect(notebookView('user-a')).toEqual({ subject: '数学' })
    clearNotebookViews()
    expect(notebookView('user-a')).toEqual({})
  })
  it('所有学习入口是已注册页面且目录内没有重复目的', () => {
    const routes = JSON.parse(readFileSync('src/pages.json', 'utf8')).pages.map(
      (p: any) => '/' + p.path,
    )
    const urls = learningSections.flatMap((s) => s.items.map((i) => i.url))
    expect(new Set(urls).size).toBe(urls.length)
    urls.forEach((url) => expect(routes).toContain(url.split('?')[0]))
  })
  it('顶层导航复用历史，去新模块时替换当前页而不增加栈', () => {
    const navigateBack = vi.fn(),
      redirectTo = vi.fn()
    vi.stubGlobal('uni', { navigateBack, redirectTo })
    vi.stubGlobal('getCurrentPages', () => [
      { route: 'pages/index/index' },
      { route: 'pages/detail/detail' },
    ])
    switchSection('/pages/index/index')
    expect(navigateBack).toHaveBeenCalledWith({ delta: 1 })
    switchSection('/pages/learning/learning')
    expect(redirectTo).toHaveBeenCalledWith({ url: '/pages/learning/learning' })
  })
})
