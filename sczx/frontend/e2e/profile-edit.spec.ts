// Migrated from the original frontend/e2e suite; expectations retained.
import { test, expect } from '@playwright/test'
const API =
  process.env.SCZX_API_URL ||
  `http://127.0.0.1:${process.env.SCZX_BACKEND_PORT || '8000'}/api/v1`
test('个人资料编辑、持久保存及邮箱修改验证', async ({ page, request }, info) => {
  const suffix = Date.now()
  const email = `profile-${suffix}@example.test`
  const nextEmail = `profile-new-${suffix}@example.test`
  const password = 'Profile-test-123'
  const registered = await request.post(API + '/auth/register', {
    data: { email, password, name: '资料测试', grade: '初二' },
  })
  expect(registered.ok()).toBeTruthy()
  const raw = await registered.json()
  const token = (raw.data || raw).access_token
  const headers = { Authorization: `Bearer ${token}` }
  await page.addInitScript(
    (value) => localStorage.setItem('minddimension_access_token', JSON.stringify(value)),
    token,
  )
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto('/#/pages/profile/profile')
  await page.getByRole('button', { name: '编辑个人资料', exact: true }).click()
  await page.getByLabel('昵称', { exact: true }).fill('新的昵称')
  await page.getByLabel('邮箱', { exact: true }).fill(nextEmail)
  await page.getByRole('combobox', { name: '年级', exact: true }).selectOption('初三')
  await page.getByLabel('当前密码', { exact: true }).fill(password)
  await page.getByRole('button', { name: '保存资料', exact: true }).click()
  await expect(page.getByRole('status')).toHaveText('已保存')
  await page.screenshot({ path: info.outputPath('edit.png'), fullPage: true })
  await page.getByRole('button', { name: '返回', exact: true }).click()
  await expect(page.locator('.profile-name')).toHaveText('新的昵称')
  await expect(page.locator('.student-profile')).not.toContainText(nextEmail)
  await expect(page.locator('.profile-meta')).toContainText('初三')
  await page.reload()
  await expect(page.locator('.student-profile')).not.toContainText(nextEmail)
  await page.screenshot({ path: info.outputPath('profile.png'), fullPage: true })
  expect(
    (await request.post(API + '/auth/login', { data: { email: nextEmail, password } })).ok(),
  ).toBeTruthy()
  expect((await request.post(API + '/auth/login', { data: { email, password } })).ok()).toBeFalsy()
  const bad = await request.patch(API + '/auth/me', {
    headers,
    data: { name: '不应保存', email, grade: '高一', current_password: 'wrong' },
  })
  expect(bad.status()).toBe(422)
  const current = await (await request.get(API + '/auth/me', { headers })).json()
  expect((current.data || current).name).toBe('新的昵称')
  const prefs = await (await request.get(API + '/student-preferences', { headers })).json()
  expect((prefs.data || prefs).grade).toBe('初三')
  expect(
    (await request.patch(API + '/auth/me', { headers, data: { grade: '小学' } })).status(),
  ).toBe(422)
  const takenEmail = `taken-${suffix}@example.test`
  expect(
    (
      await request.post(API + '/auth/register', {
        data: { email: takenEmail, password, name: '另一账号', grade: '初一' },
      })
    ).ok(),
  ).toBeTruthy()
  expect(
    (
      await request.patch(API + '/auth/me', {
        headers,
        data: { email: takenEmail, name: '不应保存', grade: '高一', current_password: password },
      })
    ).status(),
  ).toBe(409)
  const unchanged = await (await request.get(API + '/auth/me', { headers })).json()
  expect((unchanged.data || unchanged).name).toBe('新的昵称')
  expect((unchanged.data || unchanged).email).toBe(nextEmail)
})
