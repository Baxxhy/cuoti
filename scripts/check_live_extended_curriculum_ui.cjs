// Read-only rendering check of the authored actual-model samples.
const fs = require('node:fs')
const path = require('node:path')
const root = path.resolve(__dirname, '..')
const { chromium, expect } = require(path.join(root, 'frontend/node_modules/@playwright/test'))
let stage = 'launch'

async function main() {
  const folder = path.join(root, '.runtime/extended-curriculum')
  const report = JSON.parse(fs.readFileSync(path.join(folder, 'report.json'), 'utf8'))
  const credentials = JSON.parse(fs.readFileSync(path.join(folder, 'login.json'), 'utf8'))
  const browser = await chromium.launch({
    executablePath: path.join(root, 'frontend/.playwright-browsers/chromium-1234/chrome-linux64/chrome'),
    args: ['--no-sandbox'],
    env: { ...process.env, LD_LIBRARY_PATH: path.join(root, 'frontend/.playwright-libs/root/usr/lib/x86_64-linux-gnu') },
  })
  try {
    const page = await browser.newPage({ viewport: { width: 390, height: 900 } })
    const errors = []
    page.on('pageerror', () => errors.push('pageerror'))
    const response = await page.request.post('http://127.0.0.1:5174/api/v1/auth/login', { data: credentials })
    expect(response.status()).toBe(200)
    const token = (await response.json()).data.access_token
    await page.addInitScript(value => localStorage.setItem('minddimension_access_token', value), token)
    for (const key of ['radical-extraneous', 'speed-units', 'biology-correct']) {
      stage = key
      const entry = report.cases.find(row => row.key === key)
      expect(entry.diagnose).toBeTruthy()
      await page.goto(`http://127.0.0.1:5174/#/pages/diagnosis/diagnosis?id=${entry.question_id}`)
      // A hash-only goto on the same uni-app page does not create a new page
      // lifecycle; reload tests each public deep link with its own actual ID.
      await page.reload()
      if (key === 'biology-correct') {
        await expect(page.getByText('当前诊断未发现错误', { exact: true })).toBeVisible()
      } else {
        await expect(page.getByText('参考修正（待核对）', { exact: true })).toBeVisible()
        await expect(page.locator('.evidence-caption')).toContainText('尚未经本地规则验证')
        await expect(page.locator('.student-thought')).toContainText(entry.input.student_steps[1])
        await expect(page.locator('.summary-title')).not.toContainText('\\text')
      }
      for (const width of [360, 390, 1280]) {
        await page.setViewportSize({ width, height: 900 })
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
        if (key === 'speed-units' && width === 390) {
          await page.screenshot({ path: path.join(root, 'docs/final/screenshots/extended-curriculum-physics.png'), fullPage: true })
        }
      }
      console.log(`${key}: 实际渲染及3种宽度通过`)
    }
    const sample = report.cases.find(row => row.key === 'speed-units')
    const coreRoutes = [
      ['今日', '/pages/index/index', '个人易错地图'],
      ['学习', '/pages/learning/learning', '这次，解决反复卡住的地方。'],
      ['易错地图', '/pages/error-map/error-map', '把重复的问题，连起来看。'],
      ['修复路线', `/pages/repair/repair?id=${sample.question_id}`, '这道题，逐步修复。'],
    ]
    for (const [name, route, heading] of coreRoutes) {
      stage = name
      await page.goto(`http://127.0.0.1:5174/#${route}`)
      await page.reload()
      await expect(page.getByText(heading, { exact: true })).toBeVisible()
      if (name === '修复路线') {
        await expect(page.locator('.repair-timeline .katex').first()).toBeVisible()
        await expect(page.locator('.repair-timeline')).toContainText('原题已独立完成')
      }
      for (const width of [390, 1280]) {
        await page.setViewportSize({ width, height: 900 })
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
        if (name === '修复路线' && width === 390) {
          await page.screenshot({ path: path.join(root, 'docs/final/screenshots/repair-formula-mobile.png'), fullPage: true })
        }
      }
      console.log(`${name}: 当前账号实际内容及2种宽度通过`)
    }
    expect(errors).toHaveLength(0)
    console.log('诊断9组、核心页面8组尺寸检查通过，脚本错误0；未修改题目或学习记录。')
  } finally {
    await browser.close()
  }
}

main().catch(error => {
  fs.writeFileSync(path.join(root, '.runtime/extended-curriculum/ui-error.txt'), String(error.message), { mode: 0o600 })
  console.error(`实际界面核验失败：${stage}；细节仅存本机，未输出账号或凭据。`)
  process.exitCode = 1
})
