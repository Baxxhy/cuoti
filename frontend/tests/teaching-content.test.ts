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
