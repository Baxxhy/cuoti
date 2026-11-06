// Original acceptance; native routes, storage and selectors adapted.
import { expect, test, type Page } from '@playwright/test'

const API =
  process.env.SCZX_API_URL ||
  `http://127.0.0.1:${process.env.SCZX_BACKEND_PORT || '8000'}/api/v1`
async function payload(response: any) {
  expect(response.ok(), `HTTP ${response.status()}`).toBeTruthy()
  const body = await response.json()
  return body.data ?? body
}
async function login(page: Page, email: string, password: string) {
  await page.goto('/#/pages/login/login')
  await page.getByLabel('邮箱', { exact: true }).fill(email)
  await page.getByLabel('密码', { exact: true }).fill(password)
  await page.getByText('登录', { exact: true }).click()
  await expect(page).not.toHaveURL(/login\/login/)
}
function button(scope: any, text: string) {
  return scope.locator('uni-button,button').filter({ hasText: text }).first()
}
async function field(page: Page, label: string, value: string) {
  await page
    .locator('.field')
    .filter({ has: page.getByText(label, { exact: true }) })
    .locator('input,textarea')
    .first()
    .fill(value)
}

test('真实账号之间不能访问错题、试卷或管理权限，注册不能提升身份', async ({ request }) => {
  const register = async (label: string) =>
    payload(
      await request.post(API + '/auth/register', {
        data: {
          email: `qa-isolation-${label}-${Date.now()}@minddimension.local`,
          password: 'Isolated-123',
          name: label,
          grade: '初一',
          role: 'admin',
        },
      }),
    )
  const first = await register('第一学生'),
    second = await register('第二学生')
  expect(first.role).toBe('student')
  expect(second.role).toBe('student')
  const owner = { Authorization: `Bearer ${first.access_token}` },
    other = { Authorization: `Bearer ${second.access_token}` }
  const q = await payload(
    await request.post(API + '/questions/manual', {
      headers: owner,
      data: { question_text: '私有验收题：2x+3=11', subject: '数学', grade: '初一' },
    }),
  )
  expect((await request.get(API + '/questions/' + q.id, { headers: other })).status()).toBe(404)
  expect((await request.delete(API + '/questions/' + q.id, { headers: other })).status()).toBe(404)
  const paper = await payload(
    await request.post(API + '/papers', {
      headers: owner,
      data: { title: '隔离验收试卷', question_ids: [q.id] },
    }),
  )
  for (const response of [
    await request.get(API + '/papers/' + paper.id, { headers: other }),
    await request.patch(API + '/papers/' + paper.id, {
      headers: other,
      data: { title: '不应修改' },
    }),
    await request.post(API + '/papers/' + paper.id + '/export', {
      headers: other,
      data: { type: 'question_pdf' },
    }),
    await request.get(API + '/admin/workbench', { headers: other }),
  ])
    expect([403, 404]).toContain(response.status())
  expect(
    (await payload(await request.get(API + '/papers/' + paper.id, { headers: owner }))).title,
  ).toBe('隔离验收试卷')
})
