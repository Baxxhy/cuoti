// Original rendering acceptance; only storage/env adapted.
import { expect, test } from '@playwright/test'
import { randomUUID } from 'node:crypto'

test('题库图片：占位转为原位题图，选项图可选择，解析图只在交卷后出现', async ({
  page,
  request,
}, info) => {
  expect(process.env.QA_STUDY_FIGURE_SOURCE).toBeTruthy()
  // Own history: parallel bank tests must not reorder each other's records.
  const login = await request.post(process.env.SCZX_API_URL + '/auth/register', {
    data: {
      email: `bank-images-${randomUUID()}@example.test`,
      password: randomUUID(),
      name: '图片显示验收',
      grade: '初一',
    },
  })
  expect(login.ok()).toBe(true)
  const token = (await login.json()).data.access_token
  await page.addInitScript(
    (value) => localStorage.setItem('minddimension_access_token', JSON.stringify(value)),
    token,
  )
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.goto(`/#/pages/bank/bank?source_id=${process.env.QA_STUDY_FIGURE_SOURCE}`)
  await expect(page.locator('.bank-question')).toHaveCount(1)
  await expect(page.locator('.bank-question')).not.toContainText('ImageHere')
  await expect(page.locator('.image-count')).toHaveText('2 张题图')
  await page.locator('.bank-question').click()
  const stem = page.locator('.question-stem')
  await expect(stem.locator('.content-image')).toHaveCount(1)
  await expect(page.locator('.answer-options .content-image')).toHaveCount(1)
  await expect(page.locator('body')).not.toContainText('ImageHere')
  await expect(page.locator('[src*="/images/2"], [src*="/images/3"]')).toHaveCount(0)
  for (const width of [360, 390, 768, 1280]) {
    await page.setViewportSize({ width, height: 900 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    const image = stem.locator('img.content-image')
    await expect(image).toHaveJSProperty('complete', true)
    expect(await image.evaluate((node: HTMLImageElement) => node.naturalWidth)).toBeGreaterThan(0)
    await page.screenshot({
      path: info.outputPath(`question-figures-${width}.png`),
      fullPage: true,
    })
  }
  // A failed figure is visible and retryable; no silent blank space.
  const figureUrl = await stem.locator('img.content-image').getAttribute('src')
  const figurePath = new URL(figureUrl!, page.url()).pathname
  let failedOnce = false
  await page.route(
    (url) => url.pathname === figurePath,
    (route) => {
      if (!failedOnce) {
        failedOnce = true
        return route.abort()
      }
      return route.continue()
    },
  )
  await page.reload()
  await expect(stem.locator('.image-status')).toContainText('题图暂时无法加载')
  await stem.getByRole('button', { name: '重新加载', exact: true }).click()
  await expect(stem.locator('img.content-image')).toHaveJSProperty('complete', true)
  expect(
    await stem
      .locator('img.content-image')
      .evaluate((node: HTMLImageElement) => node.naturalWidth),
  ).toBeGreaterThan(0)
  // Clicking the option's figure selects that option instead of opening a lightbox.
  await page.locator('.answer-options .content-image').click()
  await expect(page.locator('.answer-options [aria-pressed="true"]')).toHaveCount(1)
  await page.getByRole('button', { name: '提交答案', exact: true }).click()
  await expect(page.locator('.result-summary')).toBeVisible()
  await expect(page.locator('.reference-solution .content-image')).toHaveCount(2)
  await expect(page.locator('body')).not.toContainText('ImageHere')
  await expect(page.getByRole('button', { name: '加入错题本', exact: true })).toHaveCount(0)
  await page.screenshot({ path: info.outputPath('solution-figures.png'), fullPage: true })
  expect(errors).toEqual([])
})
