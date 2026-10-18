import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const manifest = JSON.parse(readFileSync(resolve(process.cwd(), 'src/pages.json'), 'utf8'))
const pages = Object.fromEntries(
  manifest.pages.map((item: { path: string }) => {
    const path = resolve(process.cwd(), 'src', `${item.path}.vue`)
    return [path, readFileSync(path, 'utf8')]
  }),
)

describe('面向用户的页面文案', () => {
  it('不展示内部实现和教学流程术语', () => {
    const forbidden = [
      'MySQL',
      'Provider',
      'edge-tts',
      'faster-whisper',
      'CURRENT LEARNING STATE',
      'HUMAN CONFIRMATION',
      'COGNITIVE TWIN',
      '近迁移',
      '远迁移',
      '教回 AI',
      '受控可视化',
      '原图永久保留',
      '不会覆盖',
    ]
    for (const [path, source] of Object.entries(pages)) {
      const template = source.match(/<template[\s\S]*?<\/template>/)?.[0] || ''
      for (const term of forbidden)
        expect(template, `${path} 不应出现“${term}”`).not.toContain(term)
    }
  })
})
