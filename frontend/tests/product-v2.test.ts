import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const source = (path: string) => readFileSync(resolve(process.cwd(), `src/${path}`), 'utf8')

describe('学生端产品化 V2.0', () => {
  it('uses the task-oriented primary navigation and capture action', () => {
    const tabs = source('components/tab-bar/tab-bar.vue')
    for (const label of ['今日', '错题', '学习', '我的']) expect(tabs).toContain(label)
    expect(tabs).toContain("switchPage('/pages/capture/capture')")
    expect(tabs).toContain('type="camera-filled"')
    expect(tabs).not.toContain('<text>拍题</text>')
    expect(tabs).not.toContain("text:'分析'")
    expect(tabs).not.toContain("text:'复习'")
  })

  it('keeps navigation labels visible without a raised camera control', () => {
    const tabs = source('components/tab-bar/tab-bar.vue')
    expect(tabs).toContain('<text>录入</text>')
    expect(tabs).toContain('aria-label="录入错题"')
    expect(tabs).not.toContain('translateY(-15rpx)')
    expect(tabs).not.toContain('tab-center-button')
  })

  it('defines one shared neutral visual token system', () => {
    const styles = source('styles/uni-common.scss')
    for (const token of [
      '--color-primary: #002FA7',
      '--color-bg: #F7F7F8',
      '--color-text-primary: #202124',
    ]) {
      expect(styles.toLowerCase()).toContain(token.toLowerCase())
    }
    expect(source('App.vue')).not.toContain('--color-primary:')
  })

  it('keeps the report action-first and the profile free from local account details', () => {
    const report = source('pages/analysis/analysis.vue')
    for (const section of ['近期学习', '最需要注意', '正在稳定']) expect(report).toContain(section)
    expect(report).not.toContain('note_evidence_count')
    const profile = source('pages/profile/profile.vue')
    expect(profile).not.toContain('.local')
    expect(profile).not.toContain('当前登录身份')
  })
})
