import { chromium, type FullConfig } from '@playwright/test'
import { existsSync, readdirSync, readFileSync } from 'node:fs'
import path from 'node:path'

// Initialize the browser and compiled assets before individual interaction budgets.
// This creates no accounts, learning records or mock responses.
export default async function environmentSetup(config: FullConfig) {
  if (process.env.ZHIWEI_TEST_BUILT_H5 === '1') {
    const assets = path.resolve('dist/build/h5/assets')
    if (existsSync(assets)) {
      for (const file of readdirSync(assets)) {
        if (/\.(js|css|woff2)$/.test(file)) readFileSync(path.join(assets, file))
      }
    }
  }
  const options = config.projects[0].use
  const browser = await chromium.launch({ ...options.launchOptions, timeout: 180_000 })
  try {
    const context = await browser.newContext({ ignoreHTTPSErrors: options.ignoreHTTPSErrors })
    const page = await context.newPage()
    await page.goto(`${options.baseURL}/#/pages/login/login`, { timeout: 120_000 })
    await page.getByRole('form', { name: '登录账号', exact: true }).waitFor({ timeout: 120_000 })
    await page.evaluate(async () => {
      await document.fonts.ready
    })
  } finally {
    await browser.close()
  }
}
