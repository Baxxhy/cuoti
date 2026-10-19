import { expect, test } from 'vitest'
import { hasUsefulDefinition } from '../src/utils/knowledge-content.js'

test('知识卡不展示通用占位语，保留真正的教学定义', () => {
  expect(hasUsefulDefinition('等式基本性质是数学中用于解释和解决“方程”问题的核心知识。')).toBe(
    false,
  )
  expect(
    hasUsefulDefinition('一元一次方程是初一数学的核心学习主题，作答时要结合题目条件和本学科证据。'),
  ).toBe(false)
  expect(hasUsefulDefinition('等式两边同时除以同一个非零数，等式仍然成立。')).toBe(true)
})
