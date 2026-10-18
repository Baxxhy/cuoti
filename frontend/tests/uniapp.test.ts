import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const root = process.cwd()
const pages = JSON.parse(readFileSync(resolve(root, 'src/pages.json'), 'utf8')).pages
const source = (path: string) => readFileSync(resolve(root, 'src', path), 'utf8')

describe('UniApp 真实业务前端', () => {
  it('保留 UniApp H5/App 构建，并以真实登录作为默认入口', () => {
    const pkg = JSON.parse(readFileSync(resolve(root, 'package.json'), 'utf8'))
    expect(pkg.scripts['dev:h5']).toBe('uni')
    expect(pkg.dependencies['@dcloudio/uni-app']).toBeTruthy()
    expect(pages[0]).toEqual({ path: 'pages/login/login', style: { navigationStyle: 'custom' } })
    expect(pages.map((page: { path: string }) => page.path)).toEqual(
      expect.arrayContaining([
        'pages/index/index',
        'pages/capture/capture',
        'pages/ocr/ocr',
        'pages/tutor/tutor',
        'pages/review/review',
        'pages/practice/practice',
        'pages/problem/list',
        'pages/analysis/analysis',
      ]),
    )
    expect(existsSync(resolve(root, 'src/pages/login/login.vue'))).toBe(true)
  })

  it('真实登录页和首页通过应用 Store 读取后端数据', () => {
    expect(source('pages/login/login.vue')).toContain('store.login')
    expect(source('pages/login/login.vue')).toContain('store.restoreSession')
    expect(source('pages/index/index.vue')).toContain("getData('/dashboard')")
    expect(source('pages/index/index.vue')).toContain("go('/pages/capture/capture')")
  })
})
