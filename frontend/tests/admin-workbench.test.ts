import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { buildLearningLoop, buildSessionDistribution } from '../src/pages/admin/workbench-data.js'

const source = (path: string) => readFileSync(resolve(process.cwd(), `src/${path}`), 'utf8')

describe('管理员只读工作台', () => {
  it('maps real metrics into the learning loop', () => {
    expect(
      buildLearningLoop({
        questions: 12,
        diagnoses: 9,
        sessions: 7,
        cognitive_updates: 5,
        pending_reviews: 3,
      }),
    ).toEqual([
      { key: 'questions', label: '错题录入', value: 12, icon: 'camera-filled' },
      { key: 'diagnoses', label: '错因诊断', value: 9, icon: 'search' },
      { key: 'sessions', label: '自适应教学', value: 7, icon: 'chat-filled' },
      { key: 'cognitive_updates', label: '认知更新', value: 5, icon: 'map-filled' },
      { key: 'pending_reviews', label: '主动复习', value: 3, icon: 'calendar-filled' },
    ])
  })

  it('derives a bounded session distribution including the empty state', () => {
    expect(buildSessionDistribution({ sessions: 10, active_sessions: 4 })).toEqual({
      active: 4,
      completed: 6,
      activePercent: 40,
    })
    expect(buildSessionDistribution({ sessions: 0, active_sessions: 4 })).toEqual({
      active: 0,
      completed: 0,
      activePercent: 0,
    })
  })

  it('routes administrators to the desktop workbench', () => {
    expect(source('store/index.js')).toContain("admin: '/pages/admin/workbench'")
    expect(source('pages.json')).toContain('pages/admin/workbench')
  })

  it('shows operational evidence and never mutates project data', () => {
    const page = source('pages/admin/workbench.vue')
    for (const label of [
      '全局概览',
      '学生画像',
      '智能体轨迹',
      '认知更新',
      '系统状态',
      '学习数据闭环',
      '会话状态分布',
      '认知变化',
    ]) {
      expect(page).toContain(label)
    }
    expect(page).toContain("import { getData } from '@/api/index.js'")
    expect(page).toContain("getData('/admin/workbench')")
    expect(page).not.toContain('postData(')
    expect(page).not.toContain('patchData(')
    expect(page).not.toContain('deleteData(')
    expect(page).not.toContain('--black:')
    expect(page).not.toContain('font-family:"SFMono-Regular"')
  })
})
