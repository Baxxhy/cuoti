import { test, expect } from '@playwright/test'
import { readFileSync } from 'node:fs'
test('集合选项在确认题目和旧订正任务中完整渲染', async ({ page }, info) => {
  test.skip(!process.env.QA_OPTIONS_FIXTURE, '需要隔离的真实题目样本')
  const fixture = JSON.parse(readFileSync(process.env.QA_OPTIONS_FIXTURE!, 'utf8'))
  await page.addInitScript(
    (token) => localStorage.setItem('minddimension_access_token', token),
    fixture.token,
  )
  for (const width of [375, 1280]) {
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/#/pages/ocr/ocr?id=' + fixture.question_id)
    await expect(page.locator('.option-list .option-row')).toHaveCount(4)
    await expect(page.locator('.option-list .option-row').last().locator('.katex')).toHaveCount(1)
    await page.screenshot({ path: info.outputPath('confirm-' + width + '.png'), fullPage: true })
    await page.goto('/#/pages/task/task?id=' + fixture.task_id)
    await expect(page.locator('.teaching-content .question-option')).toHaveCount(4)
    await expect(page.locator('.question-option .katex')).toHaveCount(4)
    await expect(page.getByRole('button', { name: '答案与辅助工具', exact: true })).toBeVisible()
    await expect(page.locator('textarea')).toHaveCount(0)
    await expect(page.locator('.math-unparsed')).toHaveCount(0)
    if (fixture.figure) {
      const figure = page.locator('.teaching-content .content-image')
      await expect(figure).toHaveCount(1)
      await expect
        .poll(() => figure.locator('img').evaluate((img: HTMLImageElement) => img.naturalWidth))
        .toBeGreaterThan(0)
      const src = await figure.locator('img').getAttribute('src')
      expect(src).toContain('signature=')
      await expect(figure.locator('img')).toHaveJSProperty('complete', true)
      expect(
        await figure.locator('img').evaluate((img: HTMLImageElement) => img.naturalWidth),
      ).toBeGreaterThan(0)
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.screenshot({ path: info.outputPath('task-' + width + '.png'), fullPage: true })
    await page.reload()
    await expect(page.locator('.teaching-content .question-option')).toHaveCount(4)
    await page.locator('.question-option').first().click()
    await expect(page.getByRole('button', { name: '提交作答', exact: true })).toBeEnabled()
  }
})
