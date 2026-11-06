// Original acceptance; native routes, storage and selectors adapted.
import { expect, test } from '@playwright/test'

test('复习排版：过滤占位错因、渲染公式、紧凑拍照入口', async ({ page, request }, info) => {
  const response = await request.post(
    process.env.SCZX_API_URL + '/auth/register',
    {
      data: {
        email: `review-display-${Date.now()}@example.test`,
        password: 'ReviewDisplay-123',
        name: '排版验收',
      },
    },
  )
  expect(response.ok()).toBeTruthy()
  const body = await response.json()
  const token = (body.data || body).access_token
  await page.addInitScript(
    (value) => localStorage.setItem('minddimension_access_token', JSON.stringify(value)),
    token,
  )
  await page.route('**/api/v1/reviews/today', (route) =>
    route.fulfill({
      json: {
        data: [
          {
            id: 'display-plan',
            source_version: 'v1',
            question: {
              id: 'display-question',
              subject: '数学',
              question_text: '计算 $1+1$。',
              options: [],
            },
          },
        ],
      },
    }),
  )
  await page.route('**/api/v1/dashboard', (route) =>
    route.fulfill({
      json: {
        data: {
          misconceptions: [
            { label: 'unknown' },
            { label: 'unclassified' },
            { label: '计算 $1+1$ 时得到 $3$，正确结果是 $2$。', probability: 0.8 },
          ],
        },
      },
    }),
  )
  for (const width of [375, 768, 1280]) {
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/#/pages/review/review')
    await page.reload()
    await expect(page.getByRole('button', { name: '拍照上传作答' })).toBeVisible()
    await page.getByRole('button', { name: '巩固建议' }).click()
    await expect(page.locator('.reinforce-list .katex').first()).toBeVisible()
    await expect(page.locator('.reinforce-list')).not.toContainText(/unknown|unclassified|\$/)
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    ).toBeTruthy()
    await page.screenshot({ path: info.outputPath(`review-${width}.png`), fullPage: true })
    await page.route('**/api/v1/reviews/display-plan/attempt', (route) =>
      route.fulfill({
        json: {
          data: {
            attempt_id: 'display-attempt',
            can_update_learning: true,
            correct: true,
            student_answer: '2',
            expected_answer: '2',
            feedback: '回答正确',
          },
        },
      }),
    )
    await page.locator('.written-answer textarea').first().fill('2')
    await page.getByRole('button', { name: '提交作答', exact: true }).click()
    await expect(page.locator('.grade-grid')).toBeVisible()
    const buttons = page.locator('.grade-grid [role="button"]')
    await expect(buttons).toHaveCount(4)
    for (const button of await buttons.all()) {
      const box = await button.boundingBox()
      const label = await button.locator('span').boundingBox()
      expect(box).toBeTruthy()
      expect(label).toBeTruthy()
      expect(Math.abs(box!.y + box!.height / 2 - label!.y - label!.height / 2)).toBeLessThan(2)
      expect(Math.abs(box!.x + box!.width / 2 - label!.x - label!.width / 2)).toBeLessThan(2)
      expect(box!.height).toBe(44)
    }
    await page.screenshot({ path: info.outputPath(`review-grade-${width}.png`), fullPage: true })
  }
})
