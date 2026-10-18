import { expect, test } from '@playwright/test'

test('到期复习：草稿刷新、提交重试、判题恢复与评价丢失回执后核对历史', async ({
  page,
  request,
}, testInfo) => {
  test.skip(!process.env.QA_REVIEW_PLAN_ID, '需要隔离仓颉复习样本')
  const id = process.env.QA_REVIEW_PLAN_ID!,
    token = process.env.QA_REVIEW_TOKEN!
  await page.addInitScript(
    (value) => localStorage.setItem('minddimension_access_token', value),
    token,
  )
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(`/#/pages/review/review?plan=${id}`)
  const input = page.locator('.written-answer textarea').first()
  await input.fill('3x=15\nx=5')
  await page.reload()
  await expect(input).toHaveValue('3x=15\nx=5')
  expect(
    await page.getByRole('button', { name: '复习历史', exact: true }).getAttribute('aria-expanded'),
  ).toBe('false')
  await page.screenshot({ path: testInfo.outputPath('review-writing.png'), fullPage: true })
  const ids: string[] = []
  let submission = 0
  await page.route(`**/reviews/${id}/attempt`, async (route) => {
    ids.push(route.request().postDataJSON().request_id)
    submission++
    if (submission === 1) return route.abort('connectionreset')
    const response = await route.fetch()
    expect(response.ok()).toBe(true)
    await route.abort('connectionreset')
  })
  await page.getByRole('button', { name: '提交并判定', exact: true }).click()
  await expect(page.locator('.review-error')).toContainText('可以重试')
  await expect(input).toHaveValue('3x=15\nx=5')
  await page.waitForTimeout(2800) // Let the transient transport toast clear for the layout artifact.
  await page.screenshot({ path: testInfo.outputPath('review-retry.png'), fullPage: true })
  await page.getByRole('button', { name: '提交并判定', exact: true }).click()
  await expect(page.locator('.grade-grid')).toBeVisible()
  expect(ids).toHaveLength(2)
  expect(ids[0]).toBeTruthy()
  expect(ids[1]).toBe(ids[0])
  await expect(page.locator('.answer-result')).toContainText('回答正确')
  await page.reload()
  await expect(page.locator('.grade-grid')).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('review-result.png'), fullPage: true })
  let evaluation = 0
  await page.route(`**/reviews/${id}/grade`, async (route) => {
    evaluation++
    if (evaluation === 1) return route.abort('connectionreset')
    const response = await route.fetch()
    expect(response.ok()).toBe(true)
    await route.abort('connectionreset')
  })
  await page.getByRole('button', { name: '基本掌握', exact: true }).click()
  await expect(page.locator('.review-error')).toContainText('可以重试')
  await expect(page.locator('.grade-grid')).toBeVisible()
  await page.getByRole('button', { name: '基本掌握', exact: true }).click()
  await expect(page.getByText('本次复习已记录。', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '复习历史', exact: true }).click()
  await expect(page.locator('.list-title').filter({ hasText: '3x+2=17' })).toBeVisible()
  const history = await request.get(`${process.env.ZHIWEI_API_URL}/reviews/history`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  expect(history.ok()).toBe(true)
  expect((await history.json()).data.filter((row: any) => row.plan?.id === id)).toHaveLength(1)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})
