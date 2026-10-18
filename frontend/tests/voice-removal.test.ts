import { describe, expect, it } from 'vitest'
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const source = (path: string) => readFileSync(resolve(process.cwd(), `src/${path}`), 'utf8')

describe('前端不提供语音能力', () => {
  it('移除语音页面、入口、转写调用和状态展示', () => {
    expect(existsSync(resolve(process.cwd(), 'src/pages/voice/voice.vue'))).toBe(false)
    expect(source('pages.json')).not.toContain('pages/voice/voice')
    for (const path of [
      'pages/profile/profile.vue',
      'pages/ocr/ocr.vue',
      'pages/tutor/tutor.vue',
      'pages/system/system.vue',
      'pages/admin/workbench.vue',
    ]) {
      const page = source(path)
      expect(page).not.toContain('/voice/')
      expect(page).not.toContain('语音')
      expect(page).not.toContain('MediaRecorder')
      expect(page).not.toContain('getRecorderManager')
    }
  })
})
