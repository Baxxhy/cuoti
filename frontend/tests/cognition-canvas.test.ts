import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import CognitionCanvas from '../src/components/cognition-canvas/cognition-canvas.vue'

function context() {
  return Object.fromEntries(
    [
      'setFillStyle',
      'fillRect',
      'setStrokeStyle',
      'setLineWidth',
      'beginPath',
      'moveTo',
      'lineTo',
      'stroke',
      'draw',
    ].map((name) => [name, vi.fn()]),
  )
}
describe('知识图谱选择', () => {
  it('点击节点显示选中，再次点击解除选择；数据更新不保留旧节点', async () => {
    vi.stubGlobal('uni', { createCanvasContext: () => context() })
    const node = { id: 'k1', name: '等式的性质', category: 'knowledge' }
    const wrapper = mount(CognitionCanvas, { props: { graph: { nodes: [node], links: [] } } })
    await nextTick()
    await wrapper.find('.graph-node').trigger('click')
    expect(wrapper.emitted('select')![0][0]).toMatchObject(node)
    expect(wrapper.find('.graph-node').classes()).toContain('selected')
    await wrapper.find('.graph-node').trigger('click')
    expect(wrapper.emitted('select')!.at(-1)).toEqual([null])
    await wrapper.setProps({ graph: { nodes: [], links: [] } })
    expect(wrapper.findAll('.graph-node')).toHaveLength(0)
    expect(wrapper.text()).toContain('完成错题学习后')
    wrapper.unmount()
    vi.unstubAllGlobals()
  })
})
