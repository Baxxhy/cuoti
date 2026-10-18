import { expect, test } from '@playwright/test'

const API =
  process.env.ZHIWEI_API_URL ||
  `http://127.0.0.1:${process.env.ZHIWEI_BACKEND_PORT || '8000'}/api/v1`

test('登录：关联标签、密码管理器、持久错误和断网后原地重试', async ({ page, request }) => {
  const email = `auth-retry-${Date.now()}@example.test`
  const password = 'Account-retry-123'
  expect((await request.post(API + '/auth/register', { data: { email, password } })).ok()).toBe(
    true,
  )
  const errors: string[] = []
  page.on('pageerror', () => errors.push('runtime-error'))
  await page.goto('/#/pages/login/login')
  const emailField = page.getByLabel('邮箱', { exact: true })
  const passwordField = page.getByLabel('密码', { exact: true })
  await page.locator('label[for="login-email"]').click()
  await expect(emailField).toBeFocused()
  await expect(emailField).toHaveAttribute('autocomplete', 'username')
  await expect(passwordField).toHaveAttribute('type', 'password')
  await expect(passwordField).toHaveAttribute('autocomplete', 'current-password')
  await emailField.fill(email)
  await passwordField.fill('Wrong-password-123')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('账号或密码不正确')
  // Error feedback must remain after the transient toast disappears.
  await page.waitForTimeout(2800)
  await expect(page.getByRole('alert')).toContainText('账号或密码不正确')
  await expect(emailField).toHaveValue(email)
  await page.route('**/auth/login', (route) => route.abort('internetdisconnected'))
  await passwordField.fill(password)
  await passwordField.press('Enter')
  await expect(page.getByRole('alert')).toContainText('检查网络后重试')
  await expect(passwordField).toHaveValue(password)
  await page.unroute('**/auth/login')
  await passwordField.press('Enter')
  await expect(page).toHaveURL(/pages\/index\/index/)
  expect(errors).toEqual([])
})

test('注册：重复邮箱保留表单，修改邮箱后实际创建账号', async ({ page, request }) => {
  const email = `auth-duplicate-${Date.now()}@example.test`
  const password = 'Account-register-123'
  expect((await request.post(API + '/auth/register', { data: { email, password } })).ok()).toBe(
    true,
  )
  await page.goto('/#/pages/register/register')
  await page.getByLabel('你的名字', { exact: true }).fill('表单验收学生')
  await page.getByLabel('邮箱', { exact: true }).fill(email)
  await page.getByLabel('登录密码', { exact: true }).fill(password)
  await expect(page.getByLabel('登录密码', { exact: true })).toHaveAttribute('type', 'password')
  await expect(page.getByLabel('登录密码', { exact: true })).toHaveAttribute(
    'autocomplete',
    'new-password',
  )
  await page.getByLabel('当前年级', { exact: true }).selectOption('高一')
  await page.getByRole('button', { name: '创建账号', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('已经注册')
  await expect(page.getByLabel('你的名字', { exact: true })).toHaveValue('表单验收学生')
  await expect(page.getByLabel('当前年级', { exact: true })).toHaveValue('高一')
  await page.getByLabel('邮箱', { exact: true }).fill(`new-${email}`)
  await page.getByRole('button', { name: '创建账号', exact: true }).click()
  await expect(page).toHaveURL(/pages\/index\/index/)
})

test('修改密码：两次输入核对与失败保留，正确修改后重新登录', async ({ page, request }) => {
  const email = `auth-change-${Date.now()}@example.test`
  const oldPassword = 'Account-old-123',
    newPassword = 'Account-new-123'
  expect(
    (await request.post(API + '/auth/register', { data: { email, password: oldPassword } })).ok(),
  ).toBe(true)
  let submissions = 0
  page.on('request', (r) => {
    if (r.url().endsWith('/auth/reset-password')) submissions++
  })
  await page.goto('/#/pages/forgot/forgot')
  await page.getByLabel('账号邮箱', { exact: true }).fill(email)
  await page.getByLabel('当前密码', { exact: true }).fill('Wrong-current-123')
  await page.getByLabel('新密码', { exact: true }).fill(newPassword)
  await page.getByLabel('确认新密码', { exact: true }).fill('Different-new-123')
  await page.getByRole('button', { name: '修改密码', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('不一致')
  expect(submissions).toBe(0)
  await page.getByLabel('确认新密码', { exact: true }).fill(newPassword)
  await page.getByRole('button', { name: '修改密码', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('当前密码不正确')
  await expect(page.getByLabel('新密码', { exact: true })).toHaveValue(newPassword)
  await page.getByLabel('当前密码', { exact: true }).fill(oldPassword)
  await page.getByLabel('确认新密码', { exact: true }).press('Enter')
  await expect(page.getByText('欢迎回来', { exact: true })).toBeVisible()
  await page.getByLabel('邮箱', { exact: true }).fill(email)
  await page.getByLabel('密码', { exact: true }).fill(newPassword)
  await page.getByLabel('密码', { exact: true }).press('Enter')
  await expect(page).toHaveURL(/pages\/index\/index/)
})

test('账号页面：360至430窄屏、200%文字和缩小可视高度下输入与提交可达', async ({
  page,
}, testInfo) => {
  test.setTimeout(90_000)
  for (const width of [360, 390, 430]) {
    for (const route of ['login/login', 'register/register', 'forgot/forgot']) {
      await page.setViewportSize({ width, height: 700 })
      await page.goto('/#/pages/' + route)
      // Uni-app caches pages. Fresh styles prevent 200% compounding to 400%.
      await page.reload()
      const readyId = route.startsWith('login')
        ? 'login-email'
        : route.startsWith('register')
          ? 'register-name'
          : 'change-email'
      await expect(page.locator(`#${readyId}`)).toBeVisible()
      expect(
        await page
          .locator(`#${readyId}`)
          .evaluate((el) => parseFloat(getComputedStyle(el).fontSize)),
      ).toBe(16)
      await page.evaluate(() => {
        const sizes = [
          ...document.querySelectorAll<HTMLElement>('label,input,select,uni-text,uni-button'),
        ]
          .filter((el) => el.getClientRects().length && !el.closest('uni-icons'))
          .map((el) => [el, parseFloat(getComputedStyle(el).fontSize)] as const)
        for (const [el, size] of sizes) {
          el.style.fontSize = `${size * 2}px`
          el.style.lineHeight = '1.5'
        }
        window.scrollTo(0, 0)
      })
      expect(
        await page
          .locator(`#${readyId}`)
          .evaluate((el) => parseFloat(getComputedStyle(el).fontSize)),
      ).toBe(32)
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
        true,
      )
      expect(
        await page
          .locator('.account-input')
          .evaluateAll((fields) =>
            fields.every(
              (field) => field.clientHeight >= parseFloat(getComputedStyle(field).lineHeight),
            ),
          ),
      ).toBe(true)
      expect(
        await page.locator('.account-input').evaluateAll((fields) =>
          fields.every((field) => {
            const bounds = field.getBoundingClientRect(),
              container = field.closest('.account-field')!.getBoundingClientRect()
            return bounds.left >= container.left - 1 && bounds.right <= container.right + 1
          }),
        ),
      ).toBe(true)
      if (width === 390)
        await page.screenshot({
          path: testInfo.outputPath(`account-200-${route.split('/')[0]}.png`),
          fullPage: true,
        })
      // H5 viewport reduction checks scroll reachability; it does not simulate a native keyboard.
      await page.setViewportSize({ width, height: 360 })
      const last = page.locator('.account-input').last()
      await last.focus()
      await expect(last).toBeFocused()
      await page.locator('.primary-btn').scrollIntoViewIfNeeded()
      await expect(page.locator('.primary-btn')).toBeInViewport()
    }
  }
})
