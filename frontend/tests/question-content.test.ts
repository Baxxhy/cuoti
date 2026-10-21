import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import QuestionContent from '../src/components/question-content/question-content.vue'
import {
  questionContentBlocks,
  questionImageUrls,
  stripImageMarkers,
} from '../src/utils/question-content'
import { renderMathText } from '../src/utils/math'

vi.mock('../src/api/index.js', () => ({ mediaUrl: (url: string) => url }))
describe('题目图片与占位符', () => {
  it('真实题目中多张图与百分数公式交替出现时，不吞掉公式分隔符', () => {
    const blocks = questionContentBlocks(
      '<ImageHere>$37.5 \\%$<ImageHere>$50 \\%$<ImageHere>$24 \\%$',
      ['a.png', 'b.png', 'c.png'],
    )
    expect(blocks.filter((block) => block.kind === 'image')).toHaveLength(3)
    const formulas = blocks.filter((block) => block.kind === 'text')
    expect(formulas.map((block) => block.text)).toEqual(['$37.5 \\%$', '$50 \\%$', '$24 \\%$'])
    expect(
      formulas.every((block) => !renderMathText(block.text, true).includes('math-unparsed')),
    ).toBe(true)
  })
  it('按出现位置展示题图，保留后续条件和公式，缺图不能悄悄省略', () => {
    expect(questionContentBlocks('前文<ImageHere>后文 $x+1$<ImageHere>', ['q.png'])).toEqual([
      { kind: 'text', text: '前文' },
      { kind: 'image', url: 'q.png', index: 0 },
      { kind: 'text', text: '后文 $x+1$' },
      { kind: 'missing', index: 1 },
    ])
    expect(questionContentBlocks('题目', ['attached.png']).at(-1)).toMatchObject({
      kind: 'image',
      url: 'attached.png',
    })
  })
  it('摘要和所有公式组件不输出数据集标记，数学比较符号保持原意', () => {
    expect(stripImageMarkers('题目\n\n<ImageHere>\n\n')).toBe('题目')
    expect(stripImageMarkers('x < 2 且 y > 1')).toBe('x < 2 且 y > 1')
    const rendered = renderMathText('在 $x<2$ 时 <ImageHere> 求 $x+1$', true)
    expect(rendered).not.toContain('ImageHere')
    expect(rendered).toContain('katex')
  })
  it('题库预览包含选项图并去重，不混入答案图', () => {
    expect(
      questionImageUrls({
        image_urls: ['q.png'],
        options: [{ image_urls: ['a.png', 'q.png'] }],
        answer_image_urls: ['answer.png'],
      }),
    ).toEqual(['q.png', 'a.png'])
  })
  it('图像失败可重试，缺图明确反馈而不是空白选项', async () => {
    const page = mount(QuestionContent, { props: { text: '如图<ImageHere>', images: ['q.png'] } })
    expect(page.text()).not.toContain('ImageHere')
    await page.find('image').trigger('error')
    expect(page.find('[role="alert"]').text()).toContain('题图暂时无法加载')
    await page.find('.retry-image').trigger('click')
    expect(page.find('image').exists()).toBe(true)
    await page.setProps({ images: [] })
    expect(page.text()).toContain('题图缺失，请核对题目')
    page.unmount()
  })
})
