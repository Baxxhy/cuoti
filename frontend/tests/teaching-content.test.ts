import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import TeachingContent from '../src/components/teaching-content/teaching-content.vue'
const options = {
  global: { stubs: { 'math-text': { props: ['text'], template: '<span>{{text}}</span>' } } },
}
describe('受控教学内容块', () => {
  it('长说明按需展开，保留完整公式和条件', async () => {
    const content =
      '先看原步骤。'.repeat(25) + String.raw`$\frac{2x+3}{x}=2+\frac{3}{x}$，其中x不能为零。`
    const page = mount(TeachingContent, {
      ...options,
      props: {
        blocks: [
          { kind: 'formula', text: content },
          { kind: 'javascript', text: 'forbidden' },
        ],
      },
    })
    expect(page.text()).not.toContain(content)
    expect(page.text()).not.toContain('forbidden')
    await page.find('button').trigger('click')
    expect(page.text()).toContain(content)
    await page.find('button').trigger('click')
    expect(page.text()).not.toContain(content)
    page.unmount()
  })
  it('当前问题的长条件完整显示，不按字数截断', () => {
    const question = '完整条件'.repeat(80)
    const page = mount(TeachingContent, {
      ...options,
      props: { blocks: [{ kind: 'question', text: question }] },
    })
    expect(page.text()).toContain(question)
    expect(page.findAll('button')).toHaveLength(0)
    page.unmount()
  })
})

it('原题作答显示完整选项，切换到无选项的变式不沿用原题选项', async () => {
  const wrapper = mount(TeachingContent, {
    props: {
      blocks: [
        {
          kind: 'question',
          text: '求集合的交集',
          options: [
            { label: 'A', text: String.raw`$\{x|-2\le x<1\}$` },
            { label: 'D', text: String.raw`\{x|x<1\}` },
          ],
        },
      ],
    },
  })
  expect(wrapper.findAll('.question-option')).toHaveLength(2)
  expect(wrapper.findAll('.question-option .katex')).toHaveLength(2)
  await wrapper.setProps({ blocks: [{ kind: 'question', text: '解方程：$x+1=2$' }] })
  expect(wrapper.findAll('.question-option')).toHaveLength(0)
})

it('选择题可以点选，多选答案按题目选项顺序提交，切换题目不会带入旧选项', async () => {
  const wrapper = mount(TeachingContent, {
    props: {
      selectable: true,
      answer: '',
      blocks: [
        {
          kind: 'question',
          question_type: '多选题',
          text: '选出正确选项',
          options: [
            { label: 'A', text: '选项甲' },
            { label: 'B', text: '选项乙' },
          ],
        },
      ],
    },
  })
  await wrapper.find('checkbox-group').trigger('change', { detail: { value: ['B', 'A'] } })
  expect(wrapper.emitted('choose')?.[0]).toEqual(['A、B'])
  await wrapper.setProps({
    blocks: [
      {
        kind: 'question',
        question_type: '单选题',
        text: '选出正确选项',
        options: [
          { label: 'A', text: '选项甲' },
          { label: 'B', text: '选项乙' },
        ],
      },
    ],
  })
  await wrapper.find('radio-group').trigger('change', { detail: { value: 'B' } })
  expect(wrapper.emitted('choose')?.[1]).toEqual(['B'])
})
