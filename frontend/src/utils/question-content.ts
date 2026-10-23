const IMAGE_MARKER = /<\s*ImageHere\s*>|&lt;\s*ImageHere\s*&gt;/gi

export function stripImageMarkers(value: string) {
  if (!/<\s*ImageHere\s*>|&lt;\s*ImageHere\s*&gt;/i.test(value)) return value
  return value
    .replace(IMAGE_MARKER, '')
    .replace(/\n[ \t]*\n(?:[ \t]*\n)+/g, '\n\n')
    .trim()
}

export function questionContentBlocks(text: string, images: string[] = []) {
  const blocks: (
    | { kind: 'text'; text: string }
    | { kind: 'image'; url: string; index: number }
    | { kind: 'missing'; index: number }
  )[] = []
  let index = 0
  const parts = String(text || '').split(IMAGE_MARKER)
  parts.forEach((part, position) => {
    if (part.trim()) blocks.push({ kind: 'text', text: part.trim() })
    if (position < parts.length - 1) {
      blocks.push(
        images[index] ? { kind: 'image', url: images[index], index } : { kind: 'missing', index },
      )
      index++
    }
  })
  while (index < images.length) {
    blocks.push({ kind: 'image', url: images[index], index })
    index++
  }
  return blocks
}

export function questionImageUrls(question: any): string[] {
  const urls = question?.preview_image_urls ?? [
    ...(question?.image_urls || question?.images || []),
    ...(question?.options || []).flatMap((option: any) => option?.image_urls || []),
  ]
  return [...new Set<string>(urls)]
}
