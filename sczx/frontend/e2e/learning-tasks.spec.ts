import { expect, test } from '@playwright/test'

test('两台设备使用同一任务：远端推进后旧草稿隔离，历史仍对应原作答', async ({
  page,
  browser,
}, testInfo) => {
  expect(process.env.QA_DRAFT_QUESTION_ID, '需要隔离学习样本').toBeTruthy()
  await page.goto('/#/pages/login/login')
  await page.getByLabel('邮箱', { exact: true }).fill(process.env.QA_DRAFT_EMAIL!)
  await page.getByLabel('密码', { exact: true }).fill(process.env.QA_DRAFT_PASSWORD!)
  await page.getByText('登录', { exact: true }).click()
  await expect(page).toHaveURL(/pages\/index\/index/)
  await page.goto(`/#/pages/detail/detail?id=${process.env.QA_DRAFT_QUESTION_ID}`)
  await page.getByRole('button', { name: '订正这道题', exact: true }).click()
  await expect(page.getByText('先订正这一步', { exact: true })).toBeVisible()
  const taskURL = page.url()
  await page.locator('.answer-input textarea, textarea.answer-input').fill('11-3')
  const remoteContext = await browser.newContext({
    storageState: await page.context().storageState(),
    viewport: { width: 390, height: 844 },
  })
  try {
    const remote = await remoteContext.newPage()
    await remote.goto(taskURL)
    await expect(remote.getByText('先订正这一步', { exact: true })).toBeVisible()
    await remote.locator('.answer-input textarea, textarea.answer-input').fill('2x=8')
    await remote.getByRole('button', { name: '提交作答', exact: true }).click()
    await expect(remote.getByText('重新作答', { exact: true })).toBeVisible()
    await page.reload()
    await expect(page.getByText('重新作答', { exact: true })).toBeVisible()
    await expect(page.locator('.answer-input textarea, textarea.answer-input')).toHaveValue('')
    await expect(page.locator('[role="alert"]')).toContainText('旧草稿已单独保留')
    await page.getByRole('button', { name: /上一步草稿/ }).click()
    await expect(page.locator('.previous-draft')).toContainText('11-3')
    await page.screenshot({ path: testInfo.outputPath('task-draft-conflict.png'), fullPage: true })
    await page.getByRole('button', { name: /作答记录/ }).click()
    await expect(page.locator('.source-step')).toContainText('对应原作答第1步')
    await expect(page.locator('.source-step')).toContainText('2x=11+3')
    await page.getByRole('button', { name: /查看本次题目/ }).click()
    await expect(page.locator('.task-history')).toContainText('解方程：2x+3=11')
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  } finally {
    await remoteContext.close()
  }
})

test('学习推荐的知识卡ID可打开具体卡片，并保留结合原题讲解入口', async ({ page, request }) => {
  expect(process.env.QA_TASK_EMAIL, '需要隔离学习样本').toBeTruthy()
  const login = await request.post(process.env.SCZX_API_URL + '/auth/login', {
    data: { email: process.env.QA_TASK_EMAIL, password: process.env.QA_TASK_PASSWORD },
  })
  expect(login.ok()).toBe(true)
  const token = (await login.json()).data.access_token
  const response = await request.get(
    process.env.SCZX_API_URL + '/knowledge/cards?subject=' + encodeURIComponent('数学'),
  )
  expect(response.ok()).toBe(true)
  const card = (await response.json()).data[0]
  expect(card?.id).toBeTruthy()
  await page.addInitScript(
    (value) => localStorage.setItem('minddimension_access_token', JSON.stringify(value)),
    token,
  )
  await page.goto(
    `/#/pages/library/library?code=${encodeURIComponent(card.id)}&question=${process.env.QA_TASK_QUESTION_ID}`,
  )
  await expect(page.locator('h2')).toHaveText(card.name)
  await expect(page.getByRole('button', { name: '结合原题讲解', exact: true })).toBeVisible()
  await expect(page.getByText('知识卡暂时无法加载', { exact: true })).toHaveCount(0)
})

test('原式函数图：参数可按按钮调整、退化有说明、观察刷新后保留', async ({ page }, testInfo) => {
  expect(process.env.QA_VISUAL_QUESTION_ID, '需要隔离函数样本').toBeTruthy()
  await page.setViewportSize({ width: 360, height: 800 })
  await page.goto('/#/pages/login/login')
  await page.getByLabel('邮箱', { exact: true }).fill(process.env.QA_VISUAL_EMAIL!)
  await page.getByLabel('密码', { exact: true }).fill(process.env.QA_VISUAL_PASSWORD!)
  await page.getByText('登录', { exact: true }).click()
  await expect(page).toHaveURL(/pages\/index\/index/)
  await page.goto(`/#/pages/detail/detail?id=${process.env.QA_VISUAL_QUESTION_ID}`)
  // This fixture has no student work or localized error to "repair".
  await page.getByRole('button', { name: '订正这道题', exact: true }).click()
  await page.getByRole('button', { name: '拍照与辅助工具', exact: true }).click()
  await page.getByRole('button', { name: '查看图解', exact: true }).click()
  await page.getByText('查看', { exact: true }).last().click()
  await expect(page.locator('[data-visualization-type="quadratic_function"]')).toBeVisible()
  await page.getByRole('button', { name: '减小开口系数 a', exact: true }).click()
  await page.getByRole('button', { name: '减小开口系数 a', exact: true }).click()
  await expect(page.locator('.task-visualization')).toContainText('a为0，此时不再是二次函数')
  await page.getByRole('button', { name: '增大竖直平移 k', exact: true }).click()
  await page
    .getByRole('textbox', { name: '图示观察', exact: true })
    .fill('系数为0后成为水平线，改参数后是对照图。')
  await page.getByRole('button', { name: '保存观察', exact: true }).click()
  await expect(page.getByText('已保存这次观察。', { exact: true })).toBeVisible()
  await page.reload()
  await expect(page.locator('.task-visualization')).toContainText('竖直平移 k0.25')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: testInfo.outputPath('task-function.png'), fullPage: true })
})

test('学习达到上限后可结束回原题并创建新任务，原记录保留', async ({ page }, testInfo) => {
  expect(process.env.QA_BUDGET_TASK_ID, '需要隔离的任务上限样本').toBeTruthy()
  await page.setViewportSize({ width: 360, height: 800 })
  await page.goto('/#/pages/login/login')
  await page.getByLabel('邮箱', { exact: true }).fill(process.env.QA_BUDGET_EMAIL!)
  await page.getByLabel('密码', { exact: true }).fill(process.env.QA_BUDGET_PASSWORD!)
  await page.getByText('登录', { exact: true }).click()
  await expect(page).toHaveURL(/pages\/index\/index/)
  await page.goto(`/#/pages/task/task?id=${process.env.QA_BUDGET_TASK_ID}`)
  await expect(page.getByRole('button', { name: '结束并回原题', exact: true })).toBeVisible()
  await expect(page.locator('.answer-input')).toHaveCount(0)
  await page.screenshot({ path: testInfo.outputPath('task-budget.png'), fullPage: true })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.getByRole('button', { name: '结束并回原题', exact: true }).click()
  await page.getByText('确定', { exact: true }).last().click()
  await expect(page).toHaveURL(
    new RegExp(`pages/detail/detail\\?id=${process.env.QA_BUDGET_QUESTION_ID}`),
  )
  await page.getByRole('button', { name: '订正这道题', exact: true }).click()
  await expect(page.getByText('先订正这一步', { exact: true })).toBeVisible()
  expect(page.url()).not.toContain(process.env.QA_BUDGET_TASK_ID!)
  await page.goto(`/#/pages/task/task?id=${process.env.QA_BUDGET_TASK_ID}`)
  await expect(page.getByText('已结束', { exact: true })).toBeVisible()
})

test('不等式：诊断保留正确第一步，错误端点不判对，区间答案可提交完成', async ({
  page,
  request,
}) => {
  expect(process.env.QA_INEQUALITY_TASK_ID, '需要隔离不等式样本').toBeTruthy()
  const headers = { Authorization: `Bearer ${process.env.QA_INEQUALITY_TOKEN}` }
  await page.addInitScript(
    (token) => localStorage.setItem('minddimension_access_token', JSON.stringify(token)),
    process.env.QA_INEQUALITY_TOKEN!,
  )
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(`/#/pages/diagnosis/diagnosis?id=${process.env.QA_INEQUALITY_QUESTION_ID}`)
  await expect(page.locator('.summary-title')).toContainText('第 2 步')
  await expect(page.locator('.student-thought')).toContainText('x≤2或x≥3')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.goto(`/#/pages/task/task?id=${process.env.QA_INEQUALITY_TASK_ID}`)
  await expect(page.getByText('重新作答', { exact: true })).toBeVisible()
  await page.locator('.answer-input textarea, textarea.answer-input').fill('(x-2)(x-3)≤0')
  await page.getByRole('button', { name: '提交作答', exact: true }).click()
  await expect(page.locator('.feedback')).toContainText('取值范围')
  await expect(page.getByText('本次学习完成', { exact: true })).toHaveCount(0)
  await page.getByRole('button', { name: '继续核对', exact: true }).click()
  await page.locator('.answer-input textarea, textarea.answer-input').fill('[2,3)')
  await page.getByRole('button', { name: '提交作答', exact: true }).click()
  await expect
    .poll(async () => {
      const response = await request.get(
        `${process.env.SCZX_API_URL}/learning-tasks/${process.env.QA_INEQUALITY_TASK_ID}/history`,
        { headers },
      )
      return (await response.json()).data.items.some(
        (item: any) => item.verdict === 'confirmed_incorrect',
      )
    })
    .toBe(true)
  await expect(page.getByText('本次学习完成', { exact: true })).toHaveCount(0)
  await page.locator('.answer-input textarea, textarea.answer-input').fill('2≤x≤3')
  await page.getByRole('button', { name: '提交作答', exact: true }).click()
  await expect(page.getByText('本次学习完成', { exact: true })).toBeVisible()
  const response = await request.get(
    `${process.env.SCZX_API_URL}/learning-tasks/${process.env.QA_INEQUALITY_TASK_ID}/history`,
    { headers },
  )
  const items = (await response.json()).data.items
  expect(
    items.some((item: any) => item.verdict === 'confirmed_correct' && item.phase === 'independent'),
  ).toBe(true)
  expect(items.some((item: any) => item.verdict === 'review_required')).toBe(true)
})

test('作答图形：候选关系折叠、核对依据、刷新保留与辅助作答', async ({ page, request }) => {
  expect(process.env.QA_FIGURE_TASK_ID, '需要隔离图形标注样本').toBeTruthy()
  const token = process.env.QA_FIGURE_TOKEN!
  await page.addInitScript(
    (value) => localStorage.setItem('minddimension_access_token', JSON.stringify(value)),
    token,
  )
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(`/#/pages/task/task?id=${process.env.QA_FIGURE_TASK_ID}`)
  await expect(page.getByRole('button', { name: '查看图形标注 · 1', exact: true })).toBeVisible()
  await expect(page.locator('.figure-body')).toHaveCount(0)
  await page.getByRole('button', { name: '查看图形标注 · 1', exact: true }).focus()
  await page.keyboard.press('Enter')
  await expect(page.locator('.figure-body')).toContainText('需要检查')
  await expect(page.locator('.figure-body')).toContainText('辅助学习记录')
  await page.getByRole('button', { name: '查看核对依据', exact: true }).click()
  await expect(page.locator('.figure-basis')).toContainText('∠A=50°；∠B=60°')
  await page.locator('.answer-input textarea, textarea.answer-input').fill('70')
  await page.reload()
  await expect(page.locator('.answer-input textarea, textarea.answer-input')).toHaveValue('70')
  await expect(page.getByRole('button', { name: '查看图形标注 · 1', exact: true })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.getByRole('button', { name: '确认文字并提交', exact: true }).click()
  await expect(page.getByText('本次学习完成', { exact: true })).toBeVisible()
  const response = await request.get(
    `${process.env.SCZX_API_URL}/learning-tasks/${process.env.QA_FIGURE_TASK_ID}`,
    {
      headers: { Authorization: `Bearer ${token}` },
    },
  )
  expect(response.ok()).toBeTruthy()
  expect((await response.json()).data.learning_applied).toBe(false)
})
