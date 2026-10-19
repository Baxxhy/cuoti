import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import MathText from '../src/components/math-text/math-text.vue'

describe('公式原文核对提示', () => {
  it('坏公式保留原文及后续题句，下一条合法公式仍可渲染', () => {
    const wrapper = mount(MathText, {
      props: { text: String.raw`前文 $$\overset{⇌}$$ 后文 $x+1$`, inline: true },
    })
    expect(wrapper.find('.math-unparsed').text()).toBe(String.raw`$$\overset{⇌}$$`)
    expect(wrapper.text()).toContain('后文')
    expect(wrapper.findAll('.katex')).toHaveLength(1)
    expect(wrapper.find('[role="status"]').text()).toBe('公式原文待核对')
  })

  it('可恢复公式不显示核对提示，更新题目后清除旧提示', async () => {
    const wrapper = mount(MathText, { props: { text: '$$bad{' } })
    expect(wrapper.find('.math-notice').exists()).toBe(true)
    await wrapper.setProps({ text: String.raw`在 $$\triangleABC$$ 中`, inline: true })
    expect(wrapper.find('.math-notice').exists()).toBe(false)
    expect(wrapper.findAll('.katex')).toHaveLength(1)
    expect(wrapper.find('.katex-display').exists()).toBe(false)
  })
})
