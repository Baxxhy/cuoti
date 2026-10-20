import { expect, test } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  test.skip(!process.env.QA_PERSONAL_TOKEN, '需要隔离的长期学习验收样本')
  await page.addInitScript(
    (token) => localStorage.setItem('minddimension_access_token', token),
    process.env.QA_PERSONAL_TOKEN!,
  )
})

test('复习检索覆盖未来安排，常用范围保存与恢复，切题草稿不丢失', async ({ page }, info) => {
  await page.goto('/#/pages/review-search/review-search')
  await expect(page.locator('.review-result')).toHaveCount(20)
  await page.locator('.search-row input').first().fill('长期检索21')
  await page.getByRole('button', { name: '搜索', exact: true }).click()
  await expect(page.locator('.review-result')).toHaveCount(1)
  await expect(page.locator('.result-action')).toContainText('查看原题')
  await page.locator('.search-row input').first().fill('长期检索0')
  await page.getByRole('button', { name: '搜索', exact: true }).click()
  await expect(page.locator('.review-result')).toHaveCount(1)
  await expect(page.locator('.result-action')).toContainText('开始复习')
  await page.getByRole('button', { name: '保存当前复习范围', exact: true }).click()
  await page.locator('.range-form input').first().fill('我的方程复习')
  await page.getByRole('button', { name: '保存', exact: true }).click()
  await expect(page.getByRole('button', { name: '我的方程复习', exact: true })).toBeVisible()
  await page.reload()
  await page.getByRole('button', { name: '我的方程复习', exact: true }).click()
  await expect(page.locator('.search-row input').first()).toHaveValue('长期检索0')
  await expect(page.locator('.review-result')).toHaveCount(1)
  await page.screenshot({ path: info.outputPath('review-search-mobile.png'), fullPage: true })
  await page.locator('.review-result').click()
  await expect(page.locator('.review-question')).toContainText('长期检索0')
  const answer = page.locator('.written-answer textarea').first()
  await answer.fill('x=')
  await page.getByRole('button', { name: '数学符号', exact: true }).click()
  await page.getByRole('button', { name: '分数', exact: true }).click()
  await expect(answer).toHaveValue('x=\\frac{}{}')
  await answer.fill('x=1/2')
  await page.getByRole('button', { name: '查找复习题', exact: true }).click()
  await page.locator('.search-row input').first().fill('长期检索0')
  await page.getByRole('button', { name: '搜索', exact: true }).click()
  await page.locator('.review-result').click()
  await expect(page.locator('.written-answer textarea').first()).toHaveValue('x=1/2')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('知识框架连接真实知识卡，历史讲解恢复，模型离线时保留提问', async ({
  page,
  request,
}, info) => {
  await page.goto('/#/pages/framework/framework')
  await page.locator('.framework-search input').first().fill('长期学习验收章节')
  await expect(page.locator('.chapter')).toHaveCount(1)
  if (!(await page.locator('.knowledge-node').count()))
    await page.locator('.chapter-heading').click()
  await expect(page.locator('.knowledge-node')).toContainText('建议巩固')
  await expect(page.locator('.knowledge-node')).toContainText('1 道相关错题')
  await page.screenshot({ path: info.outputPath('framework-mobile.png'), fullPage: true })
  await page.locator('.knowledge-node').click()
  await expect(page.locator('h2')).toContainText('长期学习等式性质')
  await page.getByRole('button', { name: 'AI 老师讲解', exact: true }).click()
  await expect(page.locator('.lesson')).toContainText('受控历史讲解')
  const prompt = page.locator('.teacher-content textarea').first()
  await prompt.fill('为什么等式两边要同时运算？')
  await page.getByRole('button', { name: '发送问题', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('讲解暂时没有完成')
  await expect(prompt).toHaveValue('为什么等式两边要同时运算？')
  for (const width of [360, 768, 1280]) {
    await page.setViewportSize({ width, height: 900 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  }
  await page.screenshot({ path: info.outputPath('knowledge-teacher-desktop.png'), fullPage: true })
  const result = await request.get(`${process.env.ZHIWEI_API_URL}/knowledge/framework`, {
    headers: { Authorization: `Bearer ${process.env.QA_PERSONAL_TOKEN}` },
  })
  const node = (await result.json()).data.nodes.find(
    (item: any) => item.code === process.env.QA_PERSONAL_CODE,
  )
  expect(node.mastery.evidence_count).toBe(2)
})
