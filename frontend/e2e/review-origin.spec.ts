import { expect, test } from '@playwright/test'

async function prepare(page: any, request: any) {
  const token = process.env.QA_REVIEW_QUEUE_TOKEN!,
    id = process.env.QA_REVIEW_QUEUE_FIRST!
  await page.addInitScript(
    (value: string) => localStorage.setItem('minddimension_access_token', value),
    token,
  )
  const response = await request.get(`${process.env.ZHIWEI_API_URL}/reviews/today`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  expect(response.ok()).toBe(true)
  const plan = (await response.json()).data.find((row: any) => row.id === id)
  expect(plan).toBeTruthy()
  await page.goto(`/#/pages/review/review?plan=${id}`)
  await page.locator('.written-answer textarea').first().fill('x=3')
  await page.getByRole('button', { name: '提交并判定', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('标准答案')
  await page.getByRole('button', { name: '回原题学习', exact: true }).click()
  await expect(page).toHaveURL(new RegExp(`detail/detail\\?id=${plan.question.id}.*review=${id}`))
  await expect(page.locator('.detail-status')).toBeVisible()
  return { id, plan }
}

test('复习回原题：缺参考可进入详情，刷新详情后仍回到同题草稿', async ({
  page,
  request,
}, testInfo) => {
  test.skip(!process.env.QA_REVIEW_QUEUE_TOKEN, '需要隔离仓颉复习样本')
  const { id } = await prepare(page, request)
  await page.reload()
  await expect(page.locator('.detail-status')).toBeVisible()
  await page.getByRole('button', { name: '返回', exact: true }).click()
  await expect(page).toHaveURL(new RegExp(`review/review\\?plan=${id}`))
  await expect(page.locator('.written-answer textarea').first()).toHaveValue('x=3')
  await expect(page.locator('.previous-draft')).toHaveCount(0)
  await page.screenshot({ path: testInfo.outputPath('review-origin-return.png'), fullPage: true })
})

test('复习旧稿：来源变化呈现受控，旧文字显式采用且不自动提交', async ({
  page,
  request,
}, testInfo) => {
  test.skip(!process.env.QA_REVIEW_QUEUE_TOKEN, '需要隔离仓颉复习样本')
  const { id } = await prepare(page, request)
  let submissions = 0
  page.on('request', (request) => {
    if (request.method() === 'POST' && /\/reviews\/[^/]+\/(attempt|grade)$/.test(request.url()))
      submissions++
  })
  // Only source-version presentation is controlled; this test does not grade a fabricated version.
  await page.route('**/api/v1/reviews/today', async (route) => {
    const response = await route.fetch(),
      body = await response.json()
    body.data.find((row: any) => row.id === id).source_version = 'updated-source-presentation'
    await route.fulfill({ json: body })
  })
  await page.reload()
  await expect(page.locator('.detail-status')).toBeVisible()
  await page.getByRole('button', { name: '返回', exact: true }).click()
  const input = page.locator('.written-answer textarea').first()
  await expect(input).toHaveValue('')
  await page.getByRole('button', { name: '查看更新前的作答', exact: true }).click()
  await expect(page.locator('.previous-text')).toHaveText('x=3')
  await page.screenshot({ path: testInfo.outputPath('review-previous.png'), fullPage: true })
  await page.getByRole('button', { name: '使用这份文字', exact: true }).click()
  await expect(input).toHaveValue('x=3')
  await expect(page.locator('.previous-draft')).toHaveCount(0)
  expect(submissions).toBe(0)
  await page.reload()
  await expect(input).toHaveValue('x=3')
})
