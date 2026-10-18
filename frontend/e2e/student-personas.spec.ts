import { expect, test, type Page } from '@playwright/test'

const pageErrors = new WeakMap<Page, string[]>()
test.beforeEach(async ({ page }) => {
  const errors: string[] = []
  pageErrors.set(page, errors)
  page.on('pageerror', error => errors.push(error.message))
})
test.afterEach(async ({ page }) => {
  expect(pageErrors.get(page)).toEqual([])
})

// Three simulated behaviours, not interviews or evidence of learning efficacy.
async function login(page: Page, name: 'REPAIR' | 'REVIEW') {
  await page.goto('/#/pages/login/login')
  await page.getByLabel('邮箱', { exact: true }).fill(process.env[`QA_PERSONA_${name}_EMAIL`]!)
  await page.getByLabel('密码', { exact: true }).fill(process.env[`QA_PERSONA_${name}_PASSWORD`]!)
  await page.getByText('登录', { exact: true }).click()
  await expect(page).toHaveURL(/pages\/index\/index/)
}

test('学生甲：首次使用，改学习方向、读例题、录入与收藏，刷新后记录相符', async ({ page }, info) => {
  await page.goto('/#/pages/login/login')
  const response = await page.request.post('/api/v1/auth/register', { data: {
    email: `persona-a-${Date.now()}@example.test`, password: 'Persona-A-123456',
    name: '模拟学生甲', grade: '初一',
  } })
  expect(response.ok()).toBe(true)
  const token = (await response.json()).data.access_token
  await page.evaluate(value => localStorage.setItem('minddimension_access_token', value), token)
  await page.goto('/#/pages/index/index')
  await page.getByRole('button', { name: '选择学习方向', exact: true }).click()
  await page.getByLabel('当前学科', { exact: true }).selectOption('数学')
  await page.getByRole('button', { name: '保存学习方向', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('已保存')
  await page.getByRole('button', { name: '返回今日', exact: true }).click()
  await page.getByRole('button', { name: '选择知识与例题', exact: true }).click()
  await page.locator('.knowledge-result').first().click()
  await expect(page.getByText('理解示例', { exact: true })).toBeVisible()
  await page.goto('/#/pages/manual/manual')
  await page.locator('.field').filter({ hasText: '完整题目' }).locator('textarea').fill('求解：3x+2=17')
  await page.locator('.field').filter({ hasText: '我当时的答案' }).locator('textarea').fill('x=6')
  await page.locator('.field').filter({ hasText: '我的解题步骤' }).locator('textarea').fill('3x=17+2\nx=6')
  await page.getByText('保存并查看错题', { exact: true }).click()
  await expect(page).toHaveURL(/pages\/detail\/detail\?id=/)
  await page.getByText('收藏重点题', { exact: true }).click()
  await page.reload()
  await expect(page.getByText('取消收藏', { exact: true })).toBeVisible()
  await page.goto('/#/pages/error-map/error-map')
  await expect(page.getByText('先留下可以核对的线索', { exact: true })).toBeVisible()
  await page.screenshot({ path: info.outputPath('student-a-empty-evidence.png'), fullPage: true })
})

test('学生乙：核对首错，人工修正第1步，回放与易错地图同步且不串题', async ({ page }, info) => {
  test.skip(!process.env.QA_PERSONA_REPAIR_QUESTION_1, '需要隔离学生乙样本')
  const id = process.env.QA_PERSONA_REPAIR_QUESTION_1!
  await login(page, 'REPAIR')
  await page.goto(`/#/pages/diagnosis/diagnosis?id=${id}`)
  await page.getByText('诊断结果不对？告诉我', { exact: true }).click()
  const number = page.locator('.correction-card .field').filter({ hasText: '第几步开始出错' }).locator('input')
  await page.screenshot({ path: info.outputPath('student-b-step-number.png'), fullPage: true })
  await expect(number).toHaveValue('1')
  let invalidSubmissions = 0
  page.on('request', request => {
    if (request.method() === 'PATCH' && request.url().endsWith(`/questions/${id}/diagnosis`)) invalidSubmissions++
  })
  await number.fill('3')
  await page.getByText('保存修正', { exact: true }).click()
  await expect(page.locator('.correction-card [role="alert"]')).toContainText('实际作答中的步骤编号')
  expect(invalidSubmissions).toBe(0)
  await number.fill('1')
  await page.locator('.correction-card .field').filter({ hasText: '真正原因' }).locator('textarea').fill('我核对后发现：等式右侧应该减去3')
  const correction = `**/questions/${id}/diagnosis`
  await page.route(correction, async route => {
    if (route.request().method() === 'PATCH') return route.abort('connectionreset')
    await route.continue()
  })
  await page.getByText('保存修正', { exact: true }).click()
  await expect(page.locator('.correction-card [role="alert"]')).toBeVisible()
  await expect(number).toHaveValue('1')
  await expect(page.locator('.correction-card textarea').first()).toHaveValue('我核对后发现：等式右侧应该减去3')
  await page.unroute(correction)
  await page.getByText('保存修正', { exact: true }).click()
  await expect(page.locator('.correction-card')).not.toBeVisible()
  await page.goto(`/#/pages/replay/replay?id=${id}`)
  await expect(page.locator('.student-side')).toContainText('2x=11+3')
  await expect(page.locator('body')).toContainText('我核对后发现：等式右侧应该减去3')
  await page.goto('/#/pages/error-map/error-map')
  await expect(page.locator('.map-source')).toHaveCount(2)
  await expect(page.locator('.source-reason').filter({ hasText: '我核对后发现' })).toHaveCount(1)
  await expect(page.locator('.source-reason').filter({ hasText: '移项时应改变符号' })).toHaveCount(1)
  await page.goto(`/#/pages/diagnosis/diagnosis?id=${id}`)
  await page.getByText('诊断结果不对？告诉我', { exact: true }).click()
  await number.fill('2')
  await page.getByText('保存修正', { exact: true }).click()
  await expect(page.locator('.correction-card')).not.toBeVisible()
  await page.reload()
  await expect(page.locator('body')).toContainText('原有修复建议需要重新核对')
  await expect(page.getByText('这一步还需核对', { exact: true })).toBeVisible()
  await expect(page.getByText('当前诊断说明', { exact: true })).toBeVisible()
  await expect(page.locator('.correct-thought')).toContainText('暂无与你标记步骤对应的参考')
  await expect(page.locator('.correct-thought')).not.toContainText('等式两边先减去3')
  await expect(page.locator('.correct-thought')).not.toContainText('2x=8')
})

test('学生丙：多题到期时从本题路线进入本题复习，草稿往返和评价只影响本题', async ({ page, request }, info) => {
  test.skip(!process.env.QA_PERSONA_REVIEW_QUESTION_2, '需要隔离学生丙样本')
  const id = process.env.QA_PERSONA_REVIEW_QUESTION_2!
  const plan = process.env.QA_PERSONA_REVIEW_PLAN_2!
  await login(page, 'REVIEW')
  await page.goto(`/#/pages/repair/repair?id=${id}`)
  await page.getByRole('button', { name: '查看复习安排', exact: true }).click()
  await expect(page.locator('.review-question')).toContainText('3x+2=17')
  await expect(page).toHaveURL(new RegExp(`plan=${plan}`))
  const input = page.locator('.written-answer textarea').first()
  await input.fill('3x=15\nx=5')
  await page.reload()
  await expect(input).toHaveValue('3x=15\nx=5')
  await page.screenshot({ path: info.outputPath('student-c-review-target.png'), fullPage: true })
  // This focused harness deliberately has no model pool. Check multi-line
  // draft recovery above, then submit only the final answer for rule grading.
  // Multi-line process grading has its separate controlled-provider regression.
  await input.fill('x=5')
  await page.getByRole('button', { name: '提交并判定', exact: true }).click()
  await expect(page.locator('.answer-result')).toContainText('回答正确')
  await page.getByRole('button', { name: '基本掌握', exact: true }).click()
  await expect(page.getByText('本次复习已记录。', { exact: true })).toBeVisible()
  const token = await page.evaluate(() => localStorage.getItem('minddimension_access_token'))
  const history = await request.get(`${process.env.ZHIWEI_API_URL}/reviews/history`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  expect(history.ok()).toBe(true)
  const records = (await history.json()).data.filter((row: any) => row.plan?.id === plan)
  expect(records).toHaveLength(1)
  expect(records[0].student_answer).toBe('x=5')
  const today = await request.get(`${process.env.ZHIWEI_API_URL}/reviews/today`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  expect((await today.json()).data.map((row: any) => row.question_id)).toEqual([
    process.env.QA_PERSONA_REVIEW_QUESTION_1,
  ])
})
