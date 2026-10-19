import { expect, test } from '@playwright/test'

test('学习设置控制真实题量，练习与考试主色一致，二级页可返回', async ({ page }, info) => {
  const response = await page.request.post('/api/v1/auth/register', {
    data: {
      email: `settings-${Date.now()}@example.test`,
      password: 'Settings-123456',
      name: '设置验收',
      grade: '初一',
    },
  })
  expect(response.ok()).toBe(true)
  const actor = (await response.json()).data
  await page.addInitScript(
    (token) => localStorage.setItem('minddimension_access_token', token),
    actor.access_token,
  )
  await page.goto('/#/pages/index/index')
  await expect(page.getByText('今天先做', { exact: true })).toHaveCount(0)
  const homeColor = await page
    .locator('.focus-card .primary-btn')
    .evaluate((el) => getComputedStyle(el).backgroundColor)
  await page.getByRole('button', { name: '学习设置', exact: true }).click()
  await page.getByLabel('当前学科', { exact: true }).selectOption('数学')
  await page.getByRole('button', { name: '巩固一类题', exact: true }).click()
  await page.getByRole('button', { name: '5 分钟', exact: true }).click()
  await page.getByRole('button', { name: '保存设置', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('已保存')
  await page.getByRole('button', { name: '返回', exact: true }).click()
  await expect(page.locator('.focus-next')).toContainText('3 道题')
  await page.getByRole('button', { name: '开始练习', exact: true }).click()
  await expect(page).toHaveURL(/count=3/)
  await page.getByRole('button', { name: '返回', exact: true }).click()
  await page.getByRole('button', { name: '题库练习', exact: true }).click()
  await expect(page).toHaveURL(/count=3/)

  const pending = page.waitForResponse(
    (r) => r.request().method() === 'POST' && r.url().endsWith('/study-sessions'),
  )
  await page.getByRole('button', { name: '练 3 题', exact: true }).click()
  const created = await pending
  expect(created.ok()).toBe(true)
  expect(created.request().postDataJSON().selection_strategy).toBe('adaptive')
  const session = (await created.json()).data
  expect(session.items).toHaveLength(3)
  expect(new Set(session.items.map((item: any) => item.question.id)).size).toBe(3)
  expect(
    session.items.every(
      (item: any) => item.question.subject === '数学' && item.question.grade_band === '初中',
    ),
  ).toBe(true)
  await expect(page).toHaveURL(/pages\/study-session/)
  await page.getByRole('button', { name: '返回', exact: true }).click()
  await page.getByRole('button', { name: '模拟考试', exact: true }).click()
  await expect(page.locator('.exam-setup')).toBeVisible()
  expect(
    await page.locator('.exam-start').evaluate((el) => getComputedStyle(el).backgroundColor),
  ).toBe(homeColor)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: info.outputPath('exam-current.png'), fullPage: true })
})

// A controlled UI fixture checks event wiring; real retrieval/model evidence is tested separately.
test('参考知识可展开并打开原卡，返回后仍是当前讲解', async ({ page }) => {
  const response = await page.request.post('/api/v1/auth/register', {
    data: {
      email: `source-link-${Date.now()}@example.test`,
      password: 'SourceLink-123456',
      name: '来源入口验收',
      grade: '初一',
    },
  })
  expect(response.ok()).toBe(true)
  const actor = (await response.json()).data
  await page.addInitScript(
    (token) => localStorage.setItem('minddimension_access_token', token),
    actor.access_token,
  )
  const source = { code: 'math.equation_property', name: '等式基本性质', role: 'anchor' }
  await page.route('**/api/v1/tutor/sessions/source-link-check', (route) =>
    route.fulfill({
      json: {
        success: true,
        error: null,
        data: {
          id: 'source-link-check',
          stage: 'finished',
          state: {},
          activity: null,
          turns: [
            {
              id: 'legacy-result',
              role: 'assistant',
              content: '系统识别到你的选择为“A”，标准答案为“D”。',
              metadata_json: {},
            },
            {
              id: 'source-turn',
              role: 'assistant',
              content: '两边同时除以2。',
              metadata_json: { knowledge_sources: [source] },
            },
          ],
        },
      },
    }),
  )
  await page.route('**/api/v1/knowledge/cards/math.equation_property', (route) =>
    route.fulfill({
      json: {
        success: true,
        error: null,
        data: {
          ...source,
          subject: '数学',
          content: { definition: '等式两边同时除以同一个非零数，等式仍成立。' },
          prerequisites: [],
          next_knowledge: [],
        },
      },
    }),
  )
  await page.goto('/#/pages/tutor/tutor?id=source-link-check')
  await page.getByRole('button', { name: '查看之前的对话', exact: true }).click()
  await expect(page.getByText('应选 D。', { exact: true })).toBeVisible()
  await expect(page.locator('body')).not.toContainText('系统识别到你的选择')
  await page.locator('.source-toggle').focus()
  await page.locator('.source-toggle').press('Enter')
  await page.locator('.source-link').focus()
  await page.locator('.source-link').press('Enter')
  await expect(page).toHaveURL(/library\/library\?code=math.equation_property/)
  await expect(page.locator('h2')).toContainText('等式基本性质')
  await page.getByRole('button', { name: '返回', exact: true }).click()
  await expect(page).toHaveURL(/tutor\/tutor\?id=source-link-check/)
})
