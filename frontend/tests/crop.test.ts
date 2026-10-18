import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { containedImageBounds, createCropBox, moveCropBox, resizeCropBox } from '../src/utils/crop'

describe('拍照题目框选', () => {
  it('按照 contain 图片的真实显示区域定位，忽略上下留白', () => {
    expect(containedImageBounds(300, 400, 300, 200)).toEqual({
      left: 0,
      top: 100,
      width: 300,
      height: 200,
    })
  })

  it('支持从右下向左上拖出选框', () => {
    expect(createCropBox({ x: 0.8, y: 0.7 }, { x: 0.2, y: 0.1 })).toEqual({
      x: 0.2,
      y: 0.1,
      width: 0.6000000000000001,
      height: 0.6,
    })
  })

  it('移动和调整四角时不会越过图片边界', () => {
    const initial = { x: 0.1, y: 0.1, width: 0.5, height: 0.5 }
    expect(moveCropBox(initial, 0.8, 0.8)).toEqual({ x: 0.5, y: 0.5, width: 0.5, height: 0.5 })
    expect(resizeCropBox(initial, 'nw', { x: -1, y: -1 })).toEqual({
      x: 0,
      y: 0,
      width: 0.6,
      height: 0.6,
    })
  })

  it('裁剪页通过四个角点框选，不显示宽高滑块', () => {
    const source = readFileSync(resolve(process.cwd(), 'src/pages/crop/crop.vue'), 'utf8')
    expect(source).toContain('@touchstart.stop="startResize(handle.name, $event)"')
    expect(source).toContain('@touchmove.stop.prevent="resizeBox"')
    expect(source).toContain("{ name: 'nw'")
    expect(source).toContain("{ name: 'se'")
    expect(source).not.toContain('<slider')
    expect(source).not.toContain('宽度 {{')
    expect(source).not.toContain('高度 {{')
  })

  it('将可视框坐标映射到aspectFit图片本身，而不是整个画布', () => {
    const source = readFileSync(resolve(process.cwd(), 'src/pages/crop/crop.vue'), 'utf8')
    expect(source).toContain('containedImageBounds')
    expect(source).toContain('imageBounds.left + box.x * imageBounds.width')
    expect(source).toContain('(event.detail.x - imageBounds.left) / imageBounds.width')
    expect(source).toContain('(touch.clientY - resizeState.clientY) / imageBounds.height')
  })
})
