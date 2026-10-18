import { expect, test } from '@playwright/test'

test('持久智能体：订正、刷新草稿、独立作答、离开恢复与对照题真实完成', async ({
  page,
}, testInfo) => {
  test.skip(!process.env.QA_TASK_QUESTION_ID, '需要仓颉隔离任务样本')
  test.setTimeout(90_000)
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/#/pages/login/login')
  await page.getByLabel('邮箱', { exact: true }).fill(process.env.QA_TASK_EMAIL!)
  await page.getByLabel('密码', { exact: true }).fill(process.env.QA_TASK_PASSWORD!)
  await page.getByText('登录', { exact: true }).click()
  await expect(page).toHaveURL(/pages\/index\/index/)
  await page.goto(`/#/pages/detail/detail?id=${process.env.QA_TASK_QUESTION_ID}`)
  await page.getByRole('button', { name: '继续解决', exact: true }).click()
  await expect(page).toHaveURL(/pages\/task\/task\?id=/)
  const url = page.url()
  await expect(page.getByText('先订正这一步', { exact: true })).toBeVisible()
  await page.locator('.answer-input textarea, textarea.answer-input').fill('11-3')
  await page.screenshot({ path: testInfo.outputPath('task-repair.png'), fullPage: true })
  await page.reload()
  await expect(page.locator('.answer-input textarea, textarea.answer-input')).toHaveValue('11-3')
  await page.getByRole('button', { name: '提交', exact: true }).click()
  await expect(page.getByText('独立完成这道题', { exact: true })).toBeVisible()
  const png = await page.evaluate(() => {
    const canvas = document.createElement('canvas')
    canvas.width = 120
    canvas.height = 60
    const context = canvas.getContext('2d')!
    context.fillStyle = 'red'
    context.fillRect(0, 0, 120, 60)
    context.fillStyle = 'black'
    context.font = '20px sans-serif'
    context.fillText('x=4', 10, 35)
    return canvas.toDataURL('image/png').split(',')[1]
  })
  await expect(page.getByRole('button', { name: '拍照或选图作答', exact: true })).not.toBeVisible()
  await page.getByRole('button', { name: '更多方式', exact: true }).click()
  const chooser = page.waitForEvent('filechooser')
  await page.getByRole('button', { name: '拍照或选图作答', exact: true }).click()
  await (
    await chooser
  ).setFiles({ name: 'my-working.png', mimeType: 'image/png', buffer: Buffer.from(png, 'base64') })
  await expect(page.getByRole('button', { name: '确认文字并提交', exact: true })).toBeVisible()
  await expect(page.locator('.photo-note')).toContainText('部分字迹不清晰')
  await page.reload()
  await expect(page.locator('.answer-input textarea, textarea.answer-input')).toHaveValue('x=4')
  await page.locator('.answer-input textarea, textarea.answer-input').fill('x = 4')
  await page.screenshot({ path: testInfo.outputPath('task-handwriting.png'), fullPage: true })
  await page.getByRole('button', { name: '更多方式', exact: true }).click()
  await page.getByRole('button', { name: '用图看看', exact: true }).click()
  await page.getByText('查看', { exact: true }).last().click()
  await expect(page.locator('.task-visualization')).toBeVisible()
  await page.getByRole('button', { name: '增大两边同时减去', exact: true }).click()
  await page.getByRole('button', { name: '增大两边同时减去', exact: true }).click()
  await page
    .getByRole('textbox', { name: '图示观察', exact: true })
    .fill('两边同时减去2，等式关系仍保持。')
  await page.getByRole('button', { name: '保存观察', exact: true }).click()
  await expect(page.getByText('已保存这次观察。', { exact: true })).toBeVisible()
  await page.reload()
  await expect(page.locator('.task-visualization')).toContainText('等式两边同时减去2')
  await page.screenshot({ path: testInfo.outputPath('task-visualization.png'), fullPage: true })
  await page.getByRole('button', { name: '收起图示', exact: true }).click()
  await expect(page.locator('.answer-input textarea, textarea.answer-input')).toHaveValue('x = 4')
  await page.getByRole('button', { name: '确认文字并提交', exact: true }).click()
  await expect(page.getByText('换个条件，再试一次', { exact: true })).toBeVisible()
  await expect(page.locator('body')).not.toContainText('x=7')
  await page.goto('/#/pages/index/index')
  await page.getByRole('button', { name: '继续这一步', exact: true }).click()
  await expect(page).toHaveURL(url)
  await expect(page.getByText('换个条件，再试一次', { exact: true })).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('task-contrast.png'), fullPage: true })
  await page.getByRole('button', { name: /之前的过程/ }).click()
  await expect(page.locator('.task-history')).toContainText('11-3')
  await expect(page.locator('body')).not.toContainText('x=7')
  await page.locator('.answer-input textarea, textarea.answer-input').fill('x=7')
  await page.getByRole('button', { name: '提交', exact: true }).click()
  await expect(page.getByText('本次学习完成', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: /自检要点/ }).click()
  await page
    .getByRole('textbox', { name: '自检要点', exact: true })
    .fill('移项先检查符号，再代回原式。')
  await page.getByRole('button', { name: '确认保存', exact: true }).click()
  await expect(page.locator('.saved-note')).toContainText('移项先检查符号')
  await page.reload()
  await page.getByRole('button', { name: /自检要点/ }).click()
  await expect(page.locator('.saved-note')).toContainText('移项先检查符号')
  await page.getByRole('button', { name: '编辑', exact: true }).click()
  await page
    .getByRole('textbox', { name: '自检要点', exact: true })
    .fill('移项检查符号，除系数后代回。')
  await page.getByRole('button', { name: '确认保存', exact: true }).click()
  await expect(page.locator('.saved-note')).toContainText('除系数后代回')
  await page.getByRole('button', { name: '删除要点', exact: true }).click()
  await page.getByText('删除', { exact: true }).last().click()
  await expect(page.locator('.saved-note')).toHaveCount(0)
  await page
    .getByRole('textbox', { name: '自检要点', exact: true })
    .fill('移项检查符号，除系数后代回。')
  await page.getByRole('button', { name: '确认保存', exact: true }).click()
  await expect(page.locator('.saved-note')).toContainText('除系数后代回')
  await page.screenshot({ path: testInfo.outputPath('task-self-check.png'), fullPage: true })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.goto(`/#/pages/journey/journey?id=${process.env.QA_TASK_QUESTION_ID}`)
  await expect(page.locator('.task-records')).toContainText('本次对照已独立完成')
  await page.getByRole('button', { name: /自检要点（1）/ }).click()
  await expect(page.locator('.self-check-item')).toContainText('除系数后代回')
  await page.goto('/#/pages/task/task')
  await expect(page.locator('.history-item').first()).toContainText('解方程')
  await expect(page.locator('.history-item').first()).toContainText('本次已完成')
})

test('原式函数图：参数可按按钮调整、退化有说明、观察刷新后保留', async ({ page }, testInfo) => {
  test.skip(!process.env.QA_VISUAL_QUESTION_ID, '需要隔离函数样本')
  await page.setViewportSize({ width: 360, height: 800 })
  await page.goto('/#/pages/login/login')
  await page.getByLabel('邮箱', { exact: true }).fill(process.env.QA_VISUAL_EMAIL!)
  await page.getByLabel('密码', { exact: true }).fill(process.env.QA_VISUAL_PASSWORD!)
  await page.getByText('登录', { exact: true }).click()
  await expect(page).toHaveURL(/pages\/index\/index/)
  await page.goto(`/#/pages/detail/detail?id=${process.env.QA_VISUAL_QUESTION_ID}`)
  // This fixture has no student work or localized error to "repair".
  await page.getByRole('button', { name: '继续学习', exact: true }).click()
  await page.getByRole('button', { name: '更多方式', exact: true }).click()
  await page.getByRole('button', { name: '用图看看', exact: true }).click()
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

test('两台设备使用同一任务：远端推进后旧草稿隔离，历史仍对应原作答', async ({
  page,
  browser,
}, testInfo) => {
  test.skip(!process.env.QA_DRAFT_QUESTION_ID, '需要隔离双设备任务样本')
  await page.goto('/#/pages/login/login')
  await page.getByLabel('邮箱', { exact: true }).fill(process.env.QA_DRAFT_EMAIL!)
  await page.getByLabel('密码', { exact: true }).fill(process.env.QA_DRAFT_PASSWORD!)
  await page.getByText('登录', { exact: true }).click()
  await expect(page).toHaveURL(/pages\/index\/index/)
  await page.goto(`/#/pages/detail/detail?id=${process.env.QA_DRAFT_QUESTION_ID}`)
  await page.getByRole('button', { name: '继续解决', exact: true }).click()
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
    await remote.getByRole('button', { name: '提交', exact: true }).click()
    await expect(remote.getByText('独立完成这道题', { exact: true })).toBeVisible()
    await page.reload()
    await expect(page.getByText('独立完成这道题', { exact: true })).toBeVisible()
    await expect(page.locator('.answer-input textarea, textarea.answer-input')).toHaveValue('')
    await expect(page.locator('[role="alert"]')).toContainText('旧草稿已单独保留')
    await page.getByRole('button', { name: /上一步草稿/ }).click()
    await expect(page.locator('.previous-draft')).toContainText('11-3')
    await page.screenshot({ path: testInfo.outputPath('task-draft-conflict.png'), fullPage: true })
    await page.getByRole('button', { name: /之前的过程/ }).click()
    await expect(page.locator('.source-step')).toContainText('对应原作答第1步')
    await expect(page.locator('.source-step')).toContainText('2x=11+3')
    await page.getByRole('button', { name: /本次学习的题目/ }).click()
    await expect(page.locator('.task-history')).toContainText('解方程：2x+3=11')
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  } finally {
    await remoteContext.close()
  }
})

test('学习达到上限后可结束回原题并创建新任务，原记录保留', async ({ page }, testInfo) => {
  test.skip(!process.env.QA_BUDGET_TASK_ID, '需要隔离的任务上限样本')
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
  await page.getByRole('button', { name: '继续解决', exact: true }).click()
  await expect(page.getByText('先订正这一步', { exact: true })).toBeVisible()
  expect(page.url()).not.toContain(process.env.QA_BUDGET_TASK_ID!)
  await page.goto(`/#/pages/task/task?id=${process.env.QA_BUDGET_TASK_ID}`)
  await expect(page.getByText('已结束', { exact: true })).toBeVisible()
})

test('作答图形：候选关系折叠、核对依据、刷新保留与辅助作答', async ({ page, request }) => {
  test.skip(!process.env.QA_FIGURE_TASK_ID, '需要隔离图形标注样本')
  const token = process.env.QA_FIGURE_TOKEN!
  await page.addInitScript(
    (value) => localStorage.setItem('minddimension_access_token', value),
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
    `${process.env.ZHIWEI_API_URL}/learning-tasks/${process.env.QA_FIGURE_TASK_ID}`,
    {
      headers: { Authorization: `Bearer ${token}` },
    },
  )
  expect(response.ok()).toBeTruthy()
  expect((await response.json()).data.learning_applied).toBe(false)
})

test('不等式：诊断保留正确第一步，错误端点不判对，区间答案可提交完成', async ({
  page,
  request,
}) => {
  test.skip(!process.env.QA_INEQUALITY_TASK_ID, '需要隔离不等式样本')
  const headers = { Authorization: `Bearer ${process.env.QA_INEQUALITY_TOKEN}` }
  await page.addInitScript(
    (token) => localStorage.setItem('minddimension_access_token', token),
    process.env.QA_INEQUALITY_TOKEN!,
  )
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(`/#/pages/diagnosis/diagnosis?id=${process.env.QA_INEQUALITY_QUESTION_ID}`)
  await expect(page.locator('.summary-title')).toContainText('第 2 步')
  await expect(page.locator('.student-thought')).toContainText('x≤2或x≥3')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.goto(`/#/pages/task/task?id=${process.env.QA_INEQUALITY_TASK_ID}`)
  await expect(page.getByText('独立完成这道题', { exact: true })).toBeVisible()
  await page.locator('.answer-input textarea, textarea.answer-input').fill('(x-2)(x-3)≤0')
  await page.getByRole('button', { name: '提交', exact: true }).click()
  await expect(page.locator('.feedback')).toContainText('取值范围')
  await expect(page.getByText('本次学习完成', { exact: true })).toHaveCount(0)
  await page.getByRole('button', { name: '继续核对', exact: true }).click()
  await page.locator('.answer-input textarea, textarea.answer-input').fill('[2,3)')
  await page.getByRole('button', { name: '提交', exact: true }).click()
  await expect
    .poll(async () => {
      const response = await request.get(
        `${process.env.ZHIWEI_API_URL}/learning-tasks/${process.env.QA_INEQUALITY_TASK_ID}/history`,
        { headers },
      )
      return (await response.json()).data.items.some(
        (item: any) => item.verdict === 'confirmed_incorrect',
      )
    })
    .toBe(true)
  await expect(page.getByText('本次学习完成', { exact: true })).toHaveCount(0)
  await page.locator('.answer-input textarea, textarea.answer-input').fill('2≤x≤3')
  await page.getByRole('button', { name: '提交', exact: true }).click()
  await expect(page.getByText('本次学习完成', { exact: true })).toBeVisible()
  const response = await request.get(
    `${process.env.ZHIWEI_API_URL}/learning-tasks/${process.env.QA_INEQUALITY_TASK_ID}/history`,
    { headers },
  )
  const items = (await response.json()).data.items
  expect(
    items.some((item: any) => item.verdict === 'confirmed_correct' && item.phase === 'independent'),
  ).toBe(true)
  expect(items.some((item: any) => item.verdict === 'review_required')).toBe(true)
})
