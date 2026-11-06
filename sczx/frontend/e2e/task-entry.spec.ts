import { expect, test } from '@playwright/test'

test('未发现错误的诊断可直接进入独立任务，刷新恢复当前记录', async ({ page, request }) => {
  expect(process.env.QA_ENTRY_CLEAR_QUESTION_ID, '需要隔离正确作答样本').toBeTruthy()
  const token = process.env.QA_ENTRY_CLEAR_TOKEN || process.env.QA_ENTRY_TOKEN!
  await page.addInitScript(
    (value) => localStorage.setItem('minddimension_access_token', JSON.stringify(value)),
    token,
  )
  await page.goto(`/#/pages/diagnosis/diagnosis?id=${process.env.QA_ENTRY_CLEAR_QUESTION_ID}`)
  await expect(page.locator('.summary-title')).toContainText('未发现错误')
  await expect(page.getByRole('button', { name: '查看相关知识', exact: true })).toBeVisible()
  await page.getByRole('button', { name: '重新作答', exact: true }).click()
  await expect(page).toHaveURL(/task\/task\?id=/)
  const id = new URLSearchParams(page.url().split('?')[1]).get('id')
  await expect(page.getByText('重新作答', { exact: true })).toBeVisible()
  await page.reload()
  await expect(page).toHaveURL(new RegExp(`task/task\\?id=${id}`))
  await expect(page.getByText('重新作答', { exact: true })).toBeVisible()
  const result = await request.get(`${process.env.SCZX_API_URL}/learning-tasks/${id}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  expect(result.ok()).toBe(true)
  expect((await result.json()).data.learning_applied).toBe(false)
})
