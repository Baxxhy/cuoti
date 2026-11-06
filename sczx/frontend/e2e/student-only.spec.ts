// Original acceptance; native routes, storage and selectors adapted.
import { expect, test } from '@playwright/test'
import { readFileSync } from 'node:fs'
import path from 'node:path'

test('学生个人版没有老师家长入口，旧协作接口不可访问', async ({ page, request }) => {
  const api =
    process.env.SCZX_API_URL ||
    `http://127.0.0.1:${process.env.SCZX_BACKEND_PORT || '8002'}/api/v1`
  const registered = await request.post(api + '/auth/register', {
    data: {
      email: `personal-${Date.now()}@example.test`,
      password: 'Personal-123456',
      name: '个人错题学生',
      grade: '初二',
    },
  })
  expect(registered.ok()).toBe(true)
  const payload = await registered.json()
  const user = payload.data ?? payload
  await page.addInitScript(
    (token) => localStorage.setItem('minddimension_access_token', JSON.stringify(token)),
    user.access_token,
  )
  await page.goto('/#/pages/profile/profile')
  await expect(page.getByText('个人错题学生', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '编辑个人资料', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '学习设置', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '使用指南', exact: true })).toBeVisible()
  await expect(page.locator('.page-content')).not.toContainText(/家长|教师|关联老师|我的作业/)
  const pages = JSON.parse(readFileSync(new URL('../src/routes.json',import.meta.url), 'utf8')).map((path:string)=>({path}))
  expect(
    pages.some((entry: { path: string }) =>
      /^pages\/(teacher|guardian|assignment)\//.test(entry.path),
    ),
  ).toBe(false)
  for (const route of [
    '/teachers/classes',
    '/teachers/assignments',
    '/guardians/students',
    '/students/assignments',
    '/students/guardian-links',
  ]) {
    expect(
      (
        await request.get(api + route, {
          headers: { Authorization: `Bearer ${user.access_token}` },
        })
      ).status(),
    ).toBe(404)
  }
})
