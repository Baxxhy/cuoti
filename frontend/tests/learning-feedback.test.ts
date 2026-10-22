import { expect, test } from 'vitest'
import { learningFeedback } from '../src/utils/learning-feedback.js'

test('旧判题回执去掉系统说明，数学答案和教学解释保持原样', () => {
  expect(learningFeedback('系统识别到你的选择为“A”，标准答案为“D”。')).toBe('应选 D。')
  expect(
    learningFeedback('系统识别到的最终答案是“2”，标准答案是“$\\frac{1}{2}$”。请检查最后一行结论。'),
  ).toBe('正确答案：$\\frac{1}{2}$')
  expect(learningFeedback('选项与标准答案一致。')).toBe('选对了。')
  expect(learningFeedback('两边同时除以2，得到 $x=1/2$。')).toBe('两边同时除以2，得到 $x=1/2$。')
})

test('历史订正判错提示明确表达错误，待核验反馈保持区别', () => {
  expect(learningFeedback('这次结果还没有核对上，请检查条件和运算后再提交。')).toContain(
    '本次作答不正确',
  )
  const pending = '这次作答还需要核对。内容已保留，可以补充依据或回到原题检查。'
  expect(learningFeedback(pending)).toBe(pending)
})
