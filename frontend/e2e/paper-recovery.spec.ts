import { expect, test } from '@playwright/test'

const API =
  process.env.ZHIWEI_API_URL ||
  `http://127.0.0.1:${process.env.ZHIWEI_BACKEND_PORT || '8000'}/api/v1`
async function data(response: any) {
  expect(response.ok(), `HTTP ${response.status()}`).toBeTruthy()
  const body = await response.json()
  return body.data ?? body
}

test('组卷按最后选择打开，保存和删除失败保留编辑，窄屏操作可达', async ({
  page,
  request,
}, testInfo) => {
  let token = process.env.QA_PAPER_TOKEN || '',
    first = process.env.QA_PAPER_FIRST || '',
    second = process.env.QA_PAPER_SECOND || ''
  if (!token) {
    const user = await data(
      await request.post(API + '/auth/register', {
        data: {
          email: `qa-paper-${Date.now()}-${Math.random().toString(36).slice(2)}@example.test`,
          password: 'PaperRecovery-123',
          name: '组卷验收',
        },
      }),
    )
    token = user.access_token
    const headers = { Authorization: `Bearer ${token}` }
    const q = await data(
      await request.post(API + '/questions/manual', {
        headers,
        data: {
          question_text: '解方程：2x+3=11，写出计算过程。',
          subject: '数学',
          grade: '初一',
          student_answer: 'x=7',
        },
      }),
    )
    for (const title of ['组卷恢复甲', '组卷恢复乙']) {
      const paper = await data(
        await request.post(API + '/papers', { headers, data: { title, question_ids: [q.id] } }),
      )
      if (!first) first = paper.id
      else second = paper.id
    }
  }
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.addInitScript((value) => {
    localStorage.setItem('minddimension_access_token', value)
  }, token)
  await page.setViewportSize({ width: 375, height: 812 })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/#/pages/paper/paper-center')
  const firstRow = page.locator('.history-paper').filter({ hasText: '组卷恢复甲' }),
    secondRow = page.locator('.history-paper').filter({ hasText: '组卷恢复乙' })
  await expect(firstRow).toBeVisible()
  let release: () => void = () => {},
    started: () => void = () => {}
  const hold = new Promise<void>((resolve) => {
      release = resolve
    }),
    waiting = new Promise<void>((resolve) => {
      started = resolve
    })
  await page.route(`**/papers/${first}`, async (route) => {
    const response = await route.fetch()
    started()
    await hold
    await route.fulfill({ response })
  })
  await firstRow.click()
  await waiting
  await expect(page.getByRole('status')).toHaveText('正在打开试卷…')
  await secondRow.focus()
  await secondRow.press('Enter')
  await expect(page.locator('.editor-title input')).toHaveValue('组卷恢复乙')
  const lateResponse = page.waitForResponse((response) =>
    response.url().endsWith(`/papers/${first}`),
  )
  release()
  await lateResponse
  await page.evaluate(
    () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))),
  )
  await expect(page.locator('.editor-title input')).toHaveValue('组卷恢复乙')

  let failSave = true,
    failDelete = true
  await page.route(`**/papers/${second}`, async (route) => {
    if (route.request().method() === 'PATCH' && failSave)
      return route.fulfill({ status: 503, json: { detail: '保存连接中断，请重试' } })
    if (route.request().method() === 'DELETE' && failDelete)
      return route.fulfill({ status: 503, json: { detail: '删除未完成，请重试' } })
    return route.continue()
  })
  await page.getByLabel('当前试卷名称').fill('我的数学复习卷')
  await page.getByLabel('第1题分值').fill('15')
  const save = page.locator('uni-button,button').filter({ hasText: '保存名称、排序与分值' })
  await save.click()
  await expect(page.locator('.paper-editor [role="alert"]')).toContainText('保存连接中断')
  await expect(page.getByLabel('当前试卷名称')).toHaveValue('我的数学复习卷')
  await expect(page.getByLabel('第1题分值')).toHaveValue('15')
  await expect(page.locator('uni-toast')).not.toBeVisible()
  await expect(page.locator('.paper-editor [role="alert"]')).toContainText('保存连接中断')
  await page.evaluate(() => scrollTo(0, 0))
  await page.screenshot({ path: testInfo.outputPath('paper-save-recovery.png'), fullPage: true })
  failSave = false
  const saved = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/papers/${second}`) && response.request().method() === 'PATCH',
  )
  await save.click()
  expect((await saved).ok()).toBe(true)
  await expect(save).not.toHaveAttribute('disabled', 'true')
  await expect(page.locator('.paper-editor [role="alert"]')).toHaveCount(0)
  const stored = await data(
    await request.get(API + `/papers/${second}`, { headers: { Authorization: `Bearer ${token}` } }),
  )
  expect(stored.title).toBe('我的数学复习卷')
  expect(stored.items[0].score).toBe(15)
  await expect(page.locator('uni-toast')).not.toBeVisible()
  await page.evaluate(() => scrollTo(0, 0))
  await page.screenshot({ path: testInfo.outputPath('paper-editor.png'), fullPage: true })
  await page.getByText('删除', { exact: true }).click()
  await page.locator('.uni-modal').getByText('确定', { exact: true }).click()
  await expect(page.locator('.paper-editor [role="alert"]')).toContainText('删除未完成')
  await expect(page.getByLabel('当前试卷名称')).toHaveValue('我的数学复习卷')
  await expect(page.locator('uni-toast')).not.toBeVisible()
  for (const size of [
    { width: 375, height: 812 },
    { width: 812, height: 375 },
  ]) {
    await page.setViewportSize(size)
    await page.evaluate(() => {
      document.querySelectorAll('.paper-editor *').forEach((el) => {
        const element = el as HTMLElement
        element.style.fontSize = `${parseFloat(getComputedStyle(element).fontSize) * 2}px`
      })
    })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(
      true,
    )
    const editorBounds = await page.locator('.paper-editor').boundingBox()
    for (const field of [page.getByLabel('当前试卷名称'), page.locator('.delete-paper')]) {
      const bounds = await field.boundingBox()
      expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(editorBounds!.x + editorBounds!.width)
    }
    for (const control of await page
      .locator('.sort uni-button, .delete-paper, .export-grid uni-button')
      .all()) {
      const box = await control.boundingBox()
      expect(box!.width).toBeGreaterThanOrEqual(44)
      expect(box!.height).toBeGreaterThanOrEqual(44)
    }
    await save.scrollIntoViewIfNeeded()
    await expect(save).toBeInViewport()
    await page.evaluate(() => scrollTo(0, 0))
    await page.screenshot({
      path: testInfo.outputPath(`paper-large-${size.width}.png`),
      fullPage: true,
    })
    await page.evaluate(() =>
      document
        .querySelectorAll('.paper-editor *')
        .forEach((el) => (el as HTMLElement).style.removeProperty('font-size')),
    )
  }
  failDelete = false
  await page.getByText('删除', { exact: true }).click()
  await page.locator('.uni-modal').getByText('确定', { exact: true }).click()
  await expect(page.locator('.paper-editor')).toHaveCount(0)
  expect(errors).toEqual([])
})
