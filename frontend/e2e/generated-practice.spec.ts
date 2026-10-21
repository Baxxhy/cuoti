import { test, expect } from '@playwright/test'
import { readFileSync } from 'node:fs'
test('无题库匹配时恢复生成练习、提交并再练一道', async ({ page }, info) => {
  test.skip(!process.env.QA_GENERATED_FIXTURE, '需要真实生成练习样本')
  test.setTimeout(240000)
  const fixture = JSON.parse(readFileSync(process.env.QA_GENERATED_FIXTURE!, 'utf8'))
  await page.addInitScript(
    (token) => localStorage.setItem('minddimension_access_token', token),
    fixture.token,
  )
  await page.setViewportSize({ width: 375, height: 812 })
  const loaded = page.waitForResponse(
    (r) => r.url().endsWith('/practice/recommend') && r.request().method() === 'POST',
  )
  await page.goto('/#/pages/practice/practice?id=' + fixture.mistake_id)
  const payload = await (await loaded).json()
  const item = payload.data || payload
  await expect(page.locator('.question-card')).toBeVisible({ timeout: 120000 })
  const m = item.stem.match(/(\d+)x\+(\d+)=(-?\d+)/)!
  const answer = (Number(m[3]) - Number(m[2])) / Number(m[1])
  await page
    .locator('textarea')
    .first()
    .fill('x=' + answer)
  await page.getByRole('button', { name: '提交答案', exact: true }).click()
  await expect(page.getByText('答对了', { exact: true })).toBeVisible({ timeout: 30000 })
  await page.screenshot({ path: info.outputPath('generated-result.png'), fullPage: true })
  await page.getByRole('button', { name: '再练一道', exact: true }).click()
  await expect(page.getByRole('button', { name: '提交答案', exact: true })).toBeVisible({
    timeout: 120000,
  })
  await expect(page.locator('.question-card')).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: info.outputPath('generated-next.png'), fullPage: true })
})
