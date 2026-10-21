import { expect, test } from '@playwright/test'

test('复习排版：过滤占位错因、渲染公式、紧凑拍照入口', async ({ page, request }, info) => {
  const response = await request.post(
    'http://127.0.0.1:' + (process.env.ZHIWEI_BACKEND_PORT || '8000') + '/api/v1/auth/register',
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
    (value) => localStorage.setItem('minddimension_access_token', value),
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
  for (const width of [375, 768]) {
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
  }
})
