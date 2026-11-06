// Original acceptance; native routes, storage and selectors adapted.
import { expect, test } from '@playwright/test'
import { readFileSync } from 'node:fs'
const API =
  process.env.SCZX_API_URL ||
  `http://127.0.0.1:${process.env.SCZX_BACKEND_PORT || '8000'}/api/v1`

test('学生全路由：小屏布局、缺少题目时的反馈、个人资料返回刷新', async ({
  page,
  request,
}, info) => {
  test.setTimeout(180_000)
  const response = await request.post(`${API}/auth/register`, {
    data: {
      email: `layout-${Date.now()}@example.test`,
      password: 'LayoutAudit-123',
      name: '界面检查',
      grade: '初二',
    },
  })
  expect(response.ok()).toBeTruthy()
  const body = await response.json(),
    token = (body.data || body).access_token
  await page.addInitScript(
    (value) => localStorage.setItem('minddimension_access_token', JSON.stringify(value)),
    token,
  )
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  const routes = JSON.parse(readFileSync(new URL('../src/routes.json',import.meta.url), 'utf8'))
    .filter((route: string) => !/^pages\/(admin|system|login|register|forgot)\//.test(route))
  await page.setViewportSize({ width: 375, height: 812 })
  for (const route of routes) {
    await page.goto(`/#/${route}`)
    await expect(page.locator('.page, .tutor-page').first(), route).toBeVisible()
    await page.waitForTimeout(150)
    if (
      ['detail', 'diagnosis', 'tutor', 'visualization', 'journey'].some(
        (name) => route === `pages/${name}/${name}`,
      )
    ) {
      await expect(page.getByRole('button', { name: '选择错题', exact: true })).toBeVisible()
      await expect(page.getByText('请先选择一道错题', { exact: true })).toBeVisible()
    }
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1),
      route,
    ).toBeTruthy()
    await expect(page.locator('body'), route).not.toContainText('[object Object]')
    if (
      [
        'pages/capture/capture',
        'pages/learning/learning',
        'pages/profile/profile',
        'pages/preferences/preferences',
        'pages/review/review',
      ].includes(route)
    )
      await page.screenshot({
        path: info.outputPath(route.replaceAll('/', '-') + '.png'),
        fullPage: true,
      })
  }
  await page.goto('/#/pages/profile/profile')
  await expect(page.locator('.profile-meta')).toContainText('初二')
  await page.getByRole('button', { name: '学习设置', exact: true }).click()
  await page.locator('#current-grade').selectOption('初三')
  await page.locator('#focus-subject').selectOption('数学')
  await page.getByRole('button', { name: '保存设置', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('已保存')
  await page.getByRole('button', { name: '返回', exact: true }).click()
  await expect(page.locator('.profile-meta')).toContainText('初三')
  expect(errors).toEqual([])
})

test('学习入口分工：知识关系直达图谱，报告无重复地图，记录不含作业', async ({
  page,
  request,
}, info) => {
  const response = await request.post(`${API}/auth/register`, {
    data: {
      email: `navigation-${Date.now()}@example.test`,
      password: 'Navigation-123',
      name: '导航验收',
      grade: '初二',
    },
  })
  expect(response.ok()).toBeTruthy()
  const body = await response.json()
  await page.addInitScript(
    (value) => localStorage.setItem('minddimension_access_token', JSON.stringify(value)),
    (body.data || body).access_token,
  )
  for (const width of [375, 1280]) {
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/#/pages/learning/learning')
    await expect(page.locator('.record-shortcuts')).toContainText('订正记录')
    await expect(page.locator('.record-shortcuts')).not.toContainText(/我的作业|知识关系/)
    await expect(page.getByRole('button', { name: '知识关系', exact: true })).toHaveCount(1)
    await page.screenshot({
      path: info.outputPath(`learning-navigation-${width}.png`),
      fullPage: true,
    })
    await page.getByRole('button', { name: '知识关系', exact: true }).click()
    await expect(page.getByRole('heading', { name: '知识关系', exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: '用列表查看', exact: true })).toBeVisible()
    await expect(page.locator('.report-block, .report-empty')).toHaveCount(0)
    await page.screenshot({
      path: info.outputPath(`knowledge-relations-${width}.png`),
      fullPage: true,
    })
    await page.getByRole('button', { name: '返回', exact: true }).click()
    await page.getByRole('button', { name: '学习报告', exact: true }).click()
    await expect(page.getByRole('heading', { name: '学习报告', exact: true })).toBeVisible()
    await expect(page.locator('.report-empty')).toBeVisible()
    await expect(page.getByRole('button', { name: '易错地图', exact: true })).toHaveCount(0)
    await expect(page.locator('.relation-summary')).toHaveCount(0)
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    ).toBeTruthy()
  }
})
