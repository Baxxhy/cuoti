// Original graph geometry acceptance; independent SQL fixture, no model calls.
import { expect, test } from '@playwright/test'

test.use({ deviceScaleFactor: 1 })

test('知识图谱：实际连线对齐节点，缩放和聚焦后仍然对齐', async ({ page, request }, info) => {
  expect(process.env.QA_ROUTE_EMAIL, '需要隔离知识关系样本').toBeTruthy()
  const login = await request.post(process.env.SCZX_API_URL + '/auth/login', {
    data: { email: process.env.QA_ROUTE_EMAIL, password: process.env.QA_ROUTE_PASSWORD },
  })
  expect(login.ok()).toBe(true)
  const token = (await login.json()).data.access_token
  await page.addInitScript((value) => {
    localStorage.setItem('minddimension_access_token', JSON.stringify(value))
    const state = window as any
    state.graphLines = []
    const originalMove = CanvasRenderingContext2D.prototype.moveTo
    const originalLine = CanvasRenderingContext2D.prototype.lineTo
    CanvasRenderingContext2D.prototype.moveTo = function (x, y) {
      if (this.canvas.closest('.graph-wrap')) {
        const point = this.getTransform().transformPoint({ x, y })
        const box = this.canvas.getBoundingClientRect()
        ;(this as any).graphStart = { x: box.x + point.x, y: box.y + point.y }
      }
      originalMove.call(this, x, y)
    }
    CanvasRenderingContext2D.prototype.lineTo = function (x, y) {
      if (this.canvas.closest('.graph-wrap') && (this as any).graphStart) {
        const point = this.getTransform().transformPoint({ x, y })
        const box = this.canvas.getBoundingClientRect()
        state.graphLines.push((this as any).graphStart, { x: box.x + point.x, y: box.y + point.y })
      }
      originalLine.call(this, x, y)
    }
  }, token)
  const pageErrors: string[] = []
  page.on('pageerror', (error) => pageErrors.push(error.message))
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto('/#/pages/analysis/analysis?relations=1')
  await expect(page.getByRole('heading', { name: '知识关系', exact: true })).toBeVisible()
  await expect(page.locator('.graph-node').first()).toBeVisible()
  const verifyLines = async () => {
    await expect
      .poll(() =>
        page.evaluate(() => {
          const dots = [...document.querySelectorAll('.graph-wrap .node-dot')].map((node) => {
            const box = node.getBoundingClientRect()
            return { x: box.x + box.width / 2, y: box.y + box.height / 2 }
          })
          const lines = (window as any).graphLines as { x: number; y: number }[]
          if (!lines.length || !dots.length) return Infinity
          return Math.max(
            ...lines.map((point) =>
              Math.min(...dots.map((dot) => Math.hypot(point.x - dot.x, point.y - dot.y))),
            ),
          )
        }),
      )
      .toBeLessThan(2)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  }
  for (const width of [375, 1280]) {
    if (width !== 375) {
      await page.evaluate(() => ((window as any).graphLines = []))
      await page.setViewportSize({ width, height: 812 })
    }
    await verifyLines()
    await page.screenshot({ path: info.outputPath(`graph-aligned-${width}.png`), fullPage: true })
  }
  await page.evaluate(() => ((window as any).graphLines = []))
  await page.locator('.graph-node').first().click()
  await expect(page.locator('.graph-node.selected')).toHaveCount(1)
  await verifyLines()
  await expect(page.locator('.node-detail')).toBeVisible()
  expect(pageErrors).toEqual([])
})
