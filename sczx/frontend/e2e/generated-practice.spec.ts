import { test, expect } from '@playwright/test'
import { readFileSync } from 'node:fs'
test('无题库匹配时恢复生成练习、提交并再练一道', async ({ page, request }, info) => {
  test.setTimeout(240000)
  const API =
    process.env.SCZX_API_URL ||
    `http://127.0.0.1:${process.env.SCZX_BACKEND_PORT || '8000'}/api/v1`
  let fixture
  if (process.env.QA_GENERATED_FIXTURE)
    fixture = JSON.parse(readFileSync(process.env.QA_GENERATED_FIXTURE, 'utf8'))
  else {
    const registered = await request.post(API + '/auth/register', {
      data: {
        email: `practice-${Date.now()}@example.test`,
        password: 'Practice-test-123',
        name: '练习恢复验收',
        grade: '高三',
      },
    })
    expect(registered.ok()).toBeTruthy()
    const user = await registered.json(),
      token = (user.data || user).access_token
    const created = await request.post(API + '/questions/manual', {
      headers: { Authorization: `Bearer ${token}` },
      data: {
        subject: '数学',
        grade: '高三',
        question_text: '解方程：13x+7=98',
        student_answer: 'x=9',
      },
    })
    expect(created.ok()).toBeTruthy()
    const question = await created.json()
    fixture = { token, mistake_id: (question.data || question).id }
  }
  await page.addInitScript(
    (token) => localStorage.setItem('minddimension_access_token', JSON.stringify(token)),
    fixture.token,
  )
  await page.setViewportSize({ width: 375, height: 812 })
  const loaded = page.waitForResponse(
    (r) => r.url().endsWith('/practice/recommend') && r.request().method() === 'POST',
  )
  await page.goto('/#/pages/practice/practice?id=' + fixture.mistake_id)
  const payload = await (await loaded).json()
  const item = payload.data || payload
  await expect(page.locator('.question-card')).toBeVisible({ timeout: 120000 })
  const m = item.stem.match(/(\d+)x\+(\d+)=(-?\d+)/)!
  const answer = (Number(m[3]) - Number(m[2])) / Number(m[1])
  await page
    .locator('textarea')
    .first()
    .fill('x=' + answer)
  await page.reload()
  await expect(page.locator('textarea').first()).toHaveValue('x=' + answer)
  let failures = 0
  await page.route('**/api/v1/practice/attempt', async (route) => {
    failures++
    if (failures === 1)
      return route.fulfill({ status: 503, json: { detail: '暂时无法判题，请重试。' } })
    if (failures === 2) {
      const response = await route.fetch()
      expect(response.ok()).toBeTruthy()
      return route.abort('connectionreset')
    }
    return route.continue()
  })
  await page.getByRole('button', { name: '提交答案', exact: true }).click()
  await expect(page.locator('.practice-error')).toContainText('暂时无法判题')
  await expect(page.locator('textarea').first()).toHaveValue('x=' + answer)
  await page.getByRole('button', { name: '提交答案', exact: true }).click()
  await expect(page.locator('.practice-error')).toBeVisible()
  await page.reload()
  await expect(page.getByRole('status')).toContainText('已恢复上次的作答结果')
  await expect(page.getByText('答对了', { exact: true })).toBeVisible({ timeout: 30000 })
  await page.screenshot({ path: info.outputPath('generated-result.png'), fullPage: true })
  await page.getByRole('button', { name: '再练一道', exact: true }).click()
  await expect(page.getByRole('button', { name: '提交答案', exact: true })).toBeVisible({
    timeout: 120000,
  })
  await expect(page.locator('.question-card')).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: info.outputPath('generated-next.png'), fullPage: true })
})
