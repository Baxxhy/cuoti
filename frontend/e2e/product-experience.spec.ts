import { expect, test } from '@playwright/test'

test('产品闭环：MySQL学习方向、可追溯地图、按ID回放与真实修复任务', async ({ page }, testInfo) => {
  test.skip(!process.env.QA_EXPERIENCE_QUESTION_ID, '需要隔离仓颉产品样本')
  test.setTimeout(120_000)
  const id = process.env.QA_EXPERIENCE_QUESTION_ID!
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/#/pages/login/login')
  await page.getByLabel('邮箱', { exact: true }).fill(process.env.QA_EXPERIENCE_EMAIL!)
  await page.getByLabel('密码', { exact: true }).fill(process.env.QA_EXPERIENCE_PASSWORD!)
  await page.getByText('登录', { exact: true }).click()
  await expect(page).toHaveURL(/pages\/index\/index/)
  await expect(page.getByRole('button', { name: '查看这次修复路线', exact: true })).toBeVisible()
  await page.goto('/#/pages/preferences/preferences')
  await page.getByLabel('当前学科', { exact: true }).selectOption('数学')
  await page.getByRole('button', { name: '巩固一类题', exact: true }).click()
  await page.getByRole('button', { name: '5 分钟', exact: true }).click()
  await page.getByRole('button', { name: '保存学习方向', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('已保存')
  await page.getByRole('button', { name: '20 分钟', exact: true }).click()
  await expect(page.locator('.saved-preferences')).not.toBeVisible()
  await page.reload()
  await expect(page.getByLabel('当前学科', { exact: true })).toHaveValue('数学')
  await expect(page.getByRole('button', { name: '5 分钟', exact: true })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  await page.goto('/#/pages/index/index')
  await expect(page.locator('.home-direction')).toContainText('数学 · 巩固一类题 · 约5分钟')
  await page.screenshot({ path: testInfo.outputPath('product-home-mobile.png'), fullPage: true })
  const sourcesResponse = page.waitForResponse(response => response.url().includes('/api/v1/analytics/error-sources'))
  await page.getByRole('button', { name: /个人易错地图/ }).click()
  const actualSources = (await (await sourcesResponse).json()).data.sources
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(new Date(actualSources[0].diagnosis.created_at))
  const part = (kind: string) => parts.find(value => value.type === kind)!.value
  await expect(page.locator('.map-source .eyebrow').first()).toContainText(
    `${part('year')}-${part('month')}-${part('day')}`,
  )
  await expect(page.locator('.map-summary')).toContainText('2 道关联题目')
  await expect(page.locator('.map-source')).toHaveCount(2)
  await expect(page.locator('.source-reason').first()).toContainText('移项时应改变符号')
  for (const width of [360, 390, 1280]) {
    await page.setViewportSize({ width, height: 900 })
    await expect
      .poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth))
      .toBe(true)
    await page.screenshot({ path: testInfo.outputPath(`product-map-${width}.png`), fullPage: true })
  }
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(`/#/pages/replay/replay?id=${id}`)
  await expect(page.locator('.student-side')).toContainText('2x=11+3')
  await expect(page.locator('.reference-side')).toContainText('2x=8')
  await expect(page.locator('.reference-side')).not.toContainText('x=4')
  await page.screenshot({ path: testInfo.outputPath('product-replay-mobile.png'), fullPage: true })
  await page.getByRole('button', { name: '下一步', exact: true }).click()
  await expect(page.locator('.reference-side')).toContainText('没有可确认的步骤对应关系')
  await page.getByRole('button', { name: '上一步', exact: true }).focus()
  await page.keyboard.press('Enter')
  await expect(page.locator('.student-side')).toContainText('2x=11+3')
  await page.getByRole('button', { name: '查看修复路线', exact: true }).click()
  await expect(page.locator('.repair-step')).toHaveCount(5)
  await expect(page.locator('.repair-step').nth(2)).toContainText('待验证')
  await page.screenshot({ path: testInfo.outputPath('product-repair-mobile.png'), fullPage: true })
  await page.getByRole('button', { name: '进入学习任务', exact: true }).click()
  await expect(page).toHaveURL(/pages\/task\/task\?id=/)
  await expect(page.getByText('先订正这一步', { exact: true })).toBeVisible({ timeout: 30000 })
  expect(errors).toEqual([])
})

test('真正零历史：学习方向与真实知识卡可达；加载失败不伪装为空地图', async ({ page }, testInfo) => {
  test.skip(!process.env.QA_EXPERIENCE_QUESTION_ID, '需要隔离仓颉环境')
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/#/pages/login/login')
  const response = await page.request.post('/api/v1/auth/register', {
    data: {
      email: `cold-${Date.now()}@example.test`,
      password: 'Cold-start-123456',
      name: '首次使用验收',
      grade: '初一',
    },
  })
  expect(response.ok()).toBe(true)
  const { data } = await response.json()
  await page.evaluate(
    (token) => localStorage.setItem('minddimension_access_token', token),
    data.access_token,
  )
  await page.goto('/#/pages/index/index')
  await expect(page.locator('.home-starter')).toContainText('没带错题，也能开始')
  await page.screenshot({ path: testInfo.outputPath('product-cold-start.png'), fullPage: true })
  await page.getByRole('button', { name: '选择学习方向', exact: true }).click()
  await page.getByLabel('当前学科', { exact: true }).selectOption('数学')
  await page.getByRole('button', { name: '保存学习方向', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('已保存')
  await page.getByRole('button', { name: '返回今日', exact: true }).click()
  await page.getByRole('button', { name: '选择知识与例题', exact: true }).click()
  await expect(page).toHaveURL(/pages\/library\/library/)
  await expect(page.locator('.knowledge-result').first()).toBeVisible()
  await page.locator('.knowledge-result').first().click()
  await expect(page.getByText('理解示例', { exact: true })).toBeVisible()
  await page.goto('/#/pages/error-map/error-map')
  await expect(page.getByText('先留下可以核对的线索', { exact: true })).toBeVisible()
  await page.route('**/api/v1/analytics/error-sources*', (route) =>
    route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({ success: false, error: { message: '地图读取测试失败' } }),
    }),
  )
  await page.reload()
  await expect(page.getByText('先留下可以核对的线索', { exact: true })).not.toBeVisible()
  await expect(page.getByText('重新加载', { exact: true })).toBeVisible()
})
