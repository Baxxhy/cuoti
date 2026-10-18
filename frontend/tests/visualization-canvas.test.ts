import { expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import Canvas from '../src/components/visualization-canvas/visualization-canvas.vue'

it('画布绑定本组件ID并按实际大小缩放；天平读取实际参数', () => {
  const ctx = new Proxy({} as Record<string, any>, {
    get(target, key: string) {
      return (target[key] ||= vi.fn())
    },
  })
  const query: any = {
    in: () => query,
    select: () => query,
    boundingClientRect: (callback: any) => {
      callback({ width: 165, height: 115 })
      return query
    },
    exec: vi.fn(),
  }
  const createCanvasContext = vi.fn((_id: string, _component?: unknown) => ctx)
  vi.stubGlobal('uni', { createCanvasContext, createSelectorQuery: () => query })
  const page = mount(Canvas, {
    props: {
      canvasId: 'task-unique-canvas',
      spec: { type: 'equation_balance', parameters: { left: 17, right: 17 } },
      values: { delta: 2 },
    },
  })
  expect(createCanvasContext.mock.calls[0][0]).toBe('task-unique-canvas')
  expect(ctx.scale).toHaveBeenCalledWith(0.5, 0.5)
  expect(ctx.fillText.mock.calls.some((call: any[]) => call[0] === '17-2=15')).toBe(true)
  expect(ctx.fillText.mock.calls.some((call: any[]) => call[0] === '11-2=9')).toBe(false)
  page.unmount()
  vi.unstubAllGlobals()
})
