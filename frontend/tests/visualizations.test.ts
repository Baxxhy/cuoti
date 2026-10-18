import { describe, expect, it } from 'vitest'
import { visualizationSpecSchema, visualizationTypes } from '../src/visualizations/registry'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

describe('controlled visualization registry', () => {
  it('declares exactly 16 executable-code-free types', () => {
    expect(visualizationTypes).toHaveLength(16)
    expect(new Set(visualizationTypes).size).toBe(16)
  })

  it('rejects unknown visualization types', () => {
    expect(() =>
      visualizationSpecSchema.parse({
        schema_version: '1.0',
        type: 'model_javascript',
        title: 'bad',
        teaching_goal: 'bad',
        parameters: { code: 'alert(1)' },
        interactive_variables: [],
        highlights: [],
        annotations: [],
        student_task: 'bad',
        expected_observation: 'bad',
      }),
    ).toThrow()
  })

  it('implements an independent controlled drawer for every type', () => {
    const source = readFileSync(
      resolve(process.cwd(), 'src/components/visualization-canvas/visualization-canvas.vue'),
      'utf8',
    )
    for (const type of visualizationTypes)
      expect(source, `${type} 缺少独立绘制入口`).toContain(type)
    expect(source).not.toContain('eval(')
    expect(source).not.toContain('new Function')
  })
})
