export type CropBox = { x: number; y: number; width: number; height: number }
export type ImageBounds = { left: number; top: number; width: number; height: number }
export type CropHandle = 'nw' | 'ne' | 'sw' | 'se'

const clamp = (value: number, min = 0, max = 1) => Math.min(max, Math.max(min, value))

export function containedImageBounds(
  containerWidth: number,
  containerHeight: number,
  imageWidth: number,
  imageHeight: number,
): ImageBounds {
  if (!containerWidth || !containerHeight || !imageWidth || !imageHeight) {
    return { left: 0, top: 0, width: 0, height: 0 }
  }
  const scale = Math.min(containerWidth / imageWidth, containerHeight / imageHeight)
  const width = imageWidth * scale
  const height = imageHeight * scale
  return { left: (containerWidth - width) / 2, top: (containerHeight - height) / 2, width, height }
}

export function normalizedPoint(x: number, y: number, bounds: ImageBounds) {
  return {
    x: clamp((x - bounds.left) / bounds.width),
    y: clamp((y - bounds.top) / bounds.height),
  }
}

export function createCropBox(
  start: { x: number; y: number },
  end: { x: number; y: number },
): CropBox {
  const left = Math.min(start.x, end.x)
  const top = Math.min(start.y, end.y)
  return { x: left, y: top, width: Math.abs(end.x - start.x), height: Math.abs(end.y - start.y) }
}

export function moveCropBox(initial: CropBox, dx: number, dy: number): CropBox {
  return {
    ...initial,
    x: clamp(initial.x + dx, 0, 1 - initial.width),
    y: clamp(initial.y + dy, 0, 1 - initial.height),
  }
}

export function resizeCropBox(
  initial: CropBox,
  handle: CropHandle,
  point: { x: number; y: number },
  minimum = 0.03,
): CropBox {
  let left = initial.x
  let top = initial.y
  let right = initial.x + initial.width
  let bottom = initial.y + initial.height
  if (handle.includes('w')) left = Math.min(clamp(point.x), right - minimum)
  if (handle.includes('e')) right = Math.max(clamp(point.x), left + minimum)
  if (handle.includes('n')) top = Math.min(clamp(point.y), bottom - minimum)
  if (handle.includes('s')) bottom = Math.max(clamp(point.y), top + minimum)
  return { x: left, y: top, width: right - left, height: bottom - top }
}
