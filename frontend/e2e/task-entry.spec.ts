import { expect, test } from '@playwright/test'

test('学习入口：丢失回执可重试，诊断与详情恢复同一任务，完整讲解仍可进入', async ({ page }) => {
  test.skip(!process.env.QA_ENTRY_TASK_ID, '需要隔离学习入口样本')
  await page.addInitScript(
    (token) => localStorage.setItem('minddimension_access_token', token),
    process.env.QA_ENTRY_TOKEN!,
  )
  const questionId = process.env.QA_ENTRY_QUESTION_ID!,
    taskId = process.env.QA_ENTRY_TASK_ID!
  const requestIds: string[] = []
  let loseReceipt = true,
    guidedCalls = 0
  await page.route('**/api/v1/learning-tasks', async (route) => {
    if (route.request().method() !== 'POST') return route.continue()
    requestIds.push(route.request().postDataJSON().request_id)
    if (!loseReceipt) return route.continue()
    loseReceipt = false
    const response = await route.fetch()
    expect(response.status()).toBe(202)
    await route.abort('connectionreset')
  })
  page.on('request', (request) => {
    if (request.method() === 'POST' && request.url().endsWith('/tutor/sessions')) guidedCalls++
  })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(`/#/pages/diagnosis/diagnosis?id=${questionId}`)
  await page.getByRole('button', { name: '开始修正错误', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('请重试')
  await expect(page).toHaveURL(/diagnosis\/diagnosis/)
  await page.getByRole('button', { name: '开始修正错误', exact: true }).click()
  await expect(page).toHaveURL(new RegExp(`task/task\\?id=${taskId}`))
  await expect(page.locator('.task-title')).toBeVisible()
  expect(requestIds).toHaveLength(2)
  expect(requestIds[0]).toBe(requestIds[1])
  expect(guidedCalls).toBe(0)
  await page.locator('.answer-input textarea, textarea.answer-input').fill('入口核验未提交草稿')
  await page.reload()
  await expect(page.locator('.answer-input textarea, textarea.answer-input')).toHaveValue(
    '入口核验未提交草稿',
  )
  await page.getByRole('button', { name: '查看原题', exact: true }).click()
  await page.getByRole('button', { name: '继续解决', exact: true }).click()
  await expect(page).toHaveURL(new RegExp(`task/task\\?id=${taskId}`))
  await expect(page.locator('.answer-input textarea, textarea.answer-input')).toHaveValue(
    '入口核验未提交草稿',
  )
  expect(guidedCalls).toBe(0)
  await page.getByRole('button', { name: '查看原题', exact: true }).click()
  await page.getByRole('button', { name: '学与练', exact: true }).click()
  // Only the compatibility presentation is controlled here; its Cangjie routes
  // remain covered by the native tutor tests in the same full verification.
  await page.route('**/api/v1/tutor/sessions', (route) =>
    route.fulfill({ json: { data: { id: 'guided-entry-fixture' } } }),
  )
  await page.route('**/api/v1/tutor/sessions/guided-entry-fixture', (route) =>
    route.fulfill({
      json: {
        data: {
          id: 'guided-entry-fixture',
          stage: 'teach_back',
          status: 'active',
          knowledge_title: '等式的性质',
          activity: {
            id: 'entry-teach-back',
            type: 'teach_back',
            question: '移项为什么要变号？',
            attempt: 1,
            max_attempts: 2,
            options: [],
            keywords: [],
          },
        },
      },
    }),
  )
  await page.getByRole('button', { name: '完整引导学习', exact: false }).click()
  await expect(page).toHaveURL(/tutor\/tutor\?id=guided-entry-fixture/)
  await expect(page.locator('.activity-question')).toContainText('移项为什么要变号')
  expect(guidedCalls).toBe(1)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('未发现错误的诊断可直接进入独立任务，刷新恢复当前记录', async ({ page, request }) => {
  test.skip(!process.env.QA_ENTRY_CLEAR_QUESTION_ID, '需要隔离正确作答样本')
  const token = process.env.QA_ENTRY_CLEAR_TOKEN || process.env.QA_ENTRY_TOKEN!
  await page.addInitScript(
    (value) => localStorage.setItem('minddimension_access_token', value),
    token,
  )
  await page.goto(`/#/pages/diagnosis/diagnosis?id=${process.env.QA_ENTRY_CLEAR_QUESTION_ID}`)
  await expect(page.locator('.summary-title')).toContainText('未发现错误')
  await expect(page.getByRole('button', { name: '查看本题知识', exact: true })).toBeVisible()
  await page.getByRole('button', { name: '继续学习', exact: true }).click()
  await expect(page).toHaveURL(/task\/task\?id=/)
  const id = new URLSearchParams(page.url().split('?')[1]).get('id')
  await expect(page.getByText('独立完成这道题', { exact: true })).toBeVisible()
  await page.reload()
  await expect(page).toHaveURL(new RegExp(`task/task\\?id=${id}`))
  await expect(page.getByText('独立完成这道题', { exact: true })).toBeVisible()
  const result = await request.get(`${process.env.ZHIWEI_API_URL}/learning-tasks/${id}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  expect(result.ok()).toBe(true)
  expect((await result.json()).data.learning_applied).toBe(false)
})
