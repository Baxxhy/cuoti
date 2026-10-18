import { expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import FigureReview from '../src/components/figure-review/figure-review.vue'
const rows = [
  {
    label: '∠ACB=80°',
    status: 'conflicts',
    message: '与原题角度关系不一致，请检查标注或计算。',
    evidence_quote: '∠ACB=80°',
    source_quote: '∠A=50°；∠B=60°',
  },
  {
    label: 'AB∥CD',
    status: 'unconfirmed',
    message: '仅凭外观不能作为条件。',
    evidence_quote: 'AB∥CD',
    source_quote: '',
  },
]
const options = {
  global: {
    stubs: {
      'uni-icons': true,
      'math-text': { props: ['text'], template: '<span>{{text}}</span>' },
    },
  },
}
it('图形候选默认收起，展开后区分核对状态和辅助记录，不直接显示题目答案', async () => {
  const page = mount(FigureReview, { ...options, props: { rows } })
  expect(page.text()).toContain('查看图形标注 · 2')
  expect(page.text()).not.toContain('80°')
  await page.find('.figure-toggle').trigger('click')
  expect(page.text()).toContain('需要检查')
  expect(page.text()).toContain('待核对')
  expect(page.text()).toContain('辅助学习记录')
  expect(page.text()).not.toContain('70')
  expect(page.text()).not.toContain('∠A=50°')
  await page.find('.basis-toggle').trigger('click')
  expect(page.text()).toContain('照片转写')
  expect(page.text()).toContain('原题条件')
  expect(page.text()).toContain('∠A=50°；∠B=60°')
  await page.setProps({ rows: [rows[1]] })
  expect(page.find('.figure-body').exists()).toBe(false)
  page.unmount()
})
it('没有结构化图形观察时不显示核对入口', () => {
  const page = mount(FigureReview, options)
  expect(page.find('button').exists()).toBe(false)
  page.unmount()
})
