import { describe, expect, it } from 'vitest'
import { replaySteps, errorGroups, repairRoute } from '../src/utils/repair.js'

describe('修复功能证据边界', () => {
  it('诊断被学生纠正后，不继续把旧对齐解释当成当前错因', () => {
    const item = {
      student_steps: [{ id: 's', text: '作答' }],
      reference_steps: [{ id: 'r', text: '参考' }],
      diagnosis: {
        error_type: 'exact',
        first_error_step: null,
        user_confirmed: true,
        evidence: [
          { student_step_id: 's', reference_step_id: 'r', metadata_json: { reason: '旧错因判断' } },
        ],
      },
    }
    expect(replaySteps(item)[0].reason).not.toContain('旧错因判断')
    expect(replaySteps(item)[0].first).toBe(false)
    const corrected = {
      ...item,
      diagnosis: {
        ...item.diagnosis,
        error_type: 'calculation_error',
        first_error_step: 0,
        root_misconception: '学生核对后的新说明',
      },
    }
    expect(replaySteps(corrected)[0].reason).toBe('学生核对后的新说明')
  })
  it('按ID对齐不同顺序的参考步骤，不按行号制造对应关系', () => {
    const item = {
      student_steps: [
        { id: 's1', text: '2x=14' },
        { id: 's2', text: 'x=7' },
      ],
      reference_steps: [
        { id: 'r2', text: 'x=4' },
        { id: 'r1', text: '2x=8' },
      ],
      diagnosis: {
        error_type: 'sign_error',
        first_error_step: 0,
        root_misconception: '移项符号',
        evidence: [
          {
            student_step_id: 's1',
            reference_step_id: 'r1',
            metadata_json: { reason: '两边应同时减去3' },
          },
        ],
      },
    }
    expect(replaySteps(item)[0].references[0].text).toBe('2x=8')
    expect(replaySteps(item)[0].first).toBe(true)
    expect(replaySteps(item)[1].aligned).toBe(false)
    expect(
      replaySteps({
        ...item,
        diagnosis: { ...item.diagnosis, error_type: 'exact', first_error_step: null },
      }).some((step: any) => step.first),
    ).toBe(false)
  })
  it('没有学生步骤不补造过程，失效参考ID不猜测替代参考', () => {
    expect(replaySteps({ reference_steps: [{ id: 'r', text: '参考' }] })).toEqual([])
    expect(
      replaySteps({
        student_steps: [{ id: 's', text: '原作答' }],
        reference_steps: [{ id: 'r', text: '参考' }],
        diagnosis: { evidence: [{ student_step_id: 's', reference_step_id: 'deleted' }] },
      })[0].references,
    ).toEqual([])
  })
  it('跨题错因按学科隔离，排除未知与正确判定、同题重复记录不重复计数', () => {
    const source = (id: string, subject: string, error_type = 'sign_error') => ({
      id,
      subject,
      knowledge_points: ['方程'],
      diagnosis: { error_type, root_misconception: '需要核对' },
    })
    const groups = errorGroups([
      source('a', '数学'),
      source('a', '数学'),
      source('b', '数学'),
      source('c', '物理'),
      source('d', '数学', 'unknown'),
      source('e', '数学', 'exact'),
    ])
    expect(groups).toHaveLength(2)
    expect(groups[0].sources.map((value: any) => value.id)).toEqual(['a', 'b'])
    expect(groups[0].points).toEqual(['方程'])
  })
  it('修复路线只使用档案证据，不用浏览次数、掌握估计或练习题数冒充完成', () => {
    const item = { id: 'q', diagnosis: {}, mastery_score: 1 }
    const route = repairRoute(item, {
      stages: [
        { key: 'understanding', completed: true },
        { key: 'transfer', completed: false },
      ],
      practice: { correct: 5 },
      review: { due: 0 },
    })
    expect(route.find((step: any) => step.key === 'learn')?.state).toBe('已有理解证据')
    expect(route.find((step: any) => step.key === 'practice')?.state).toBe('待验证')
    expect(route.find((step: any) => step.key === 'review')?.url).toBe(
      '/pages/journey/journey?id=q',
    )
  })
  it('区分局部订正、原题独立和单条件对照，下一步随实际记录改变', () => {
    const item = { id: 'q', confirmed: true, analysis: {}, diagnosis: {} }
    const partial = repairRoute(item, { learning_tasks: { repair_verified: true } })
    expect(partial.find((step: any) => step.key === 'learn')?.state).toBe('已订正局部步骤')
    expect(partial.find((step: any) => step.recommended)?.key).toBe('learn')
    const original = repairRoute(item, {
      learning_tasks: { original_independent: true, near_transfer: true },
      review: { due: 1 },
    })
    expect(original.find((step: any) => step.key === 'practice')?.state).toBe('已有单条件对照证据')
    expect(original.find((step: any) => step.recommended)?.key).toBe('review')
    expect(original.find((step: any) => step.key === 'learn')?.state).toBe('原题已独立完成')
  })
  it('本题复习必须带自己的计划，不能让队列首题或上次位置替代本题', () => {
    const item = { id: 'second-question', confirmed: true, analysis: {}, diagnosis: {} }
    const route = repairRoute(item, { review: { due: 1, plan_id: 'second-plan' } })
    expect(route.find((step: any) => step.key === 'review')?.url).toBe(
      '/pages/review/review?plan=second-plan',
    )
    const stale = repairRoute(item, { review: { due: 1 } })
    expect(stale.find((step: any) => step.key === 'review')?.url).toBe(
      '/pages/journey/journey?id=second-question',
    )
  })
})
