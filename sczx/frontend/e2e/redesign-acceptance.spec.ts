import { expect, test } from '@playwright/test'
import { readFileSync, writeFileSync } from 'node:fs'
import { randomUUID } from 'node:crypto'

// All business data below is persisted by the isolated Python/MySQL backend.
// This suite does not intercept API routes or substitute model responses.
test('全站重构：全部路由在手机与桌面真实渲染，包含学生学习与维护页面', async ({
  browser,
  request,
}, info) => {
  expect(process.env.QA_ROLE_TESTS, '需要隔离角色样本').toBeTruthy()
  expect(process.env.QA_ROUTE_QUESTION_ID, '需要隔离路由样本').toBeTruthy()
  test.setTimeout(240_000)
  const API = process.env.SCZX_API_URL!
  const call = async (method: string, url: string, token = '', data?: unknown) => {
    const response = await request.fetch(API + url, {
      method,
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      ...(data === undefined ? {} : { data }),
    })
    expect(response.ok(), `${method} ${url}: ${response.status()}`).toBe(true)
    const body = await response.json()
    return body.data ?? body
  }
  const login = async (role: string) =>
    (
      await call('POST', '/auth/login', '', {
        email: process.env[`QA_${role}_EMAIL`],
        password: process.env[`QA_${role}_PASSWORD`],
      })
    ).access_token as string
  const tokens = {
    student: await login('ROUTE'),
    admin: await login('ADMIN'),
    public: '',
  }
  const qid = process.env.QA_ROUTE_QUESTION_ID!
  const tutor = await call('POST', '/tutor/sessions', tokens.student, { question_id: qid })
  const task = await call('POST', '/learning-tasks', tokens.student, {
    question_id: qid,
    request_id: randomUUID(),
  })
  const bank = await call(
    'GET',
    `/study-bank?subject=${encodeURIComponent('数学')}&source_id=${encodeURIComponent(process.env.QA_STUDY_SOURCE!)}&limit=1`,
    tokens.student,
  )
  const study = await call('POST', '/study-sessions', tokens.student, {
    mode: 'practice',
    subject: '数学',
    source_id: process.env.QA_STUDY_SOURCE,
    count: 1,
    question_ids: [bank.questions[0].id],
  })
  const imagePage = await browser.newPage()
  const png = await imagePage.evaluate(() => {
    const canvas = document.createElement('canvas')
    canvas.width = 320
    canvas.height = 200
    const ctx = canvas.getContext('2d')!
    ctx.fillStyle = '#fff'
    ctx.fillRect(0, 0, 320, 200)
    ctx.fillStyle = '#222'
    ctx.font = '26px sans-serif'
    ctx.fillText('2x + 3 = 11', 28, 65)
    ctx.fillText('2x = 11 + 3', 28, 115)
    return canvas.toDataURL('image/png').split(',')[1]
  })
  await imagePage.close()
  const ingest = await request.post(API + '/questions/ingest', {
    headers: { Authorization: `Bearer ${tokens.student}` },
    multipart: {
      defer_processing: 'true',
      file: {
        name: 'route.png',
        mimeType: 'image/png',
        buffer: Buffer.from(png, 'base64'),
      },
    },
  })
  expect(ingest.ok()).toBe(true)
  const image = (await ingest.json()).data
  const parameters: Record<string, string> = {
    'crop/crop': `id=${image.question_id}`,
    'ocr/ocr': `id=${qid}&edit=1`,
    'detail/detail': `id=${qid}`,
    'diagnosis/diagnosis': `id=${qid}`,
    'replay/replay': `id=${qid}`,
    'repair/repair': `id=${qid}`,
    'journey/journey': `id=${qid}`,
    'knowledge/knowledge': `id=${qid}`,
    'practice/practice': `id=${qid}`,
    'task/task': `id=${task.id}`,
    'tutor/tutor': `id=${tutor.id}`,
    'visualization/visualization': `id=${tutor.id}`,
    'study-session/study-session': `id=${study.id}`,
  }
  const pages = (JSON.parse(readFileSync(new URL('../src/routes.json', import.meta.url), 'utf8')) as string[]).map((path) => ({ path }))
  const results: unknown[] = [],
    errors: string[] = []
  for (const role of ['public', 'student', 'admin'] as const) {
    const context = await browser.newContext({
      baseURL: process.env.SCZX_WEB_URL,
      viewport: { width: 375, height: 812 },
      reducedMotion: 'reduce',
    })
    if (tokens[role])
      await context.addInitScript(
        (token) => localStorage.setItem('minddimension_access_token', JSON.stringify(token)),
        tokens[role],
      )
    const page = await context.newPage()
    page.on('pageerror', (error) => errors.push(error.message))
    for (const entry of pages) {
      const route = entry.path.replace(/^pages\//, '')
      const owner = /^(login|register|forgot)\//.test(route)
        ? 'public'
        : /^(admin|system)\//.test(route)
          ? 'admin'
          : 'student'
      if (role !== owner) continue
      for (const width of [375, 1280]) {
        await page.setViewportSize({ width, height: 812 })
        await page.goto(`/#/pages/${route}${parameters[route] ? '?' + parameters[route] : ''}`)
        await page.reload()
        const destination = route === 'search/search' ? 'problem/list' : route
        await expect(page).toHaveURL(new RegExp(`#/pages/${destination}(?:[?]|$)`))
        await expect(page.locator('h1').first()).toBeVisible({ timeout: 20_000 })
        await expect(page.locator('.state-panel .web-loading')).toHaveCount(0, {
          timeout: 20_000,
        })
        await expect(page.locator('.state-panel .ghost-btn')).toHaveCount(0)
        const heading = await page
          .locator('h1')
          .first()
          .evaluate((el) => {
            const style = getComputedStyle(el)
            const frame = el.closest('.app-header, .topbar')
            const rect = el.getBoundingClientRect()
            const bounds = frame?.getBoundingClientRect()
            return {
              fontSize: parseFloat(style.fontSize),
              fontWeight: Number(style.fontWeight),
              alignment: style.textAlign,
              centerOffset: bounds
                ? Math.abs(rect.x + rect.width / 2 - (bounds.x + bounds.width / 2))
                : null,
            }
          })
        if (route === 'index/index') {
          await expect(page.locator('.home-brand')).toHaveText('错题帮')
          expect(heading.fontSize, route).toBeLessThanOrEqual(20)
          expect(heading.fontWeight, route).toBeLessThanOrEqual(600)
          if (width < 1100) {
            const brand = await page.locator('.home-brand').boundingBox()
            const card = await page.locator('.focus-card').boundingBox()
            expect(Math.abs(brand!.x - card!.x), route).toBeLessThanOrEqual(2)
          } else {
            await expect(page.locator('.nav-brand')).toBeVisible()
            await expect(page.locator('.nav-brand')).toContainText('错题帮')
          }
        } else if (route !== 'login/login') {
          expect(heading.fontSize, route).toBeLessThanOrEqual(18)
          expect(heading.fontWeight, route).toBeLessThanOrEqual(600)
          expect(heading.alignment, route).toBe('center')
          expect(heading.centerOffset, route).not.toBeNull()
          expect(heading.centerOffset!, route).toBeLessThanOrEqual(48)
        }
        const field = page
          .locator(
            'input:not([type="file"]):not([type="checkbox"]):not([type="radio"]):not([type="range"]):not([type="hidden"]):not([disabled]), textarea:not([disabled]), select:not([disabled])',
          )
          .filter({ visible: true })
          .first()
        if (await field.count()) {
          await field.focus()
          expect(await field.evaluate((el) => getComputedStyle(el).outlineStyle), route).toBe(
            'none',
          )
          await field.blur()
          await page.evaluate(() => window.scrollTo(0, 0))
        }
        expect(
          await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
          `${route} at ${width}`,
        ).toBe(true)
        if (route === 'detail/detail') {
          await expect(page.locator('.detail-figure')).toHaveCount(1)
          await expect(page.locator('img.detail-figure')).toHaveJSProperty('complete', true)
          expect(
            await page
              .locator('img.detail-figure')
              .evaluate((img: HTMLImageElement) => img.naturalWidth),
          ).toBeGreaterThan(0)
        }
        await page.evaluate(async () => {
          await document.fonts.ready
          await new Promise<void>((resolve) =>
            requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
          )
        })
        await page.screenshot({
          path: info.outputPath(`${route.replaceAll('/', '-')}-${width}.png`),
          fullPage: true,
        })
        results.push({
          route,
          width,
          title: await page.locator('h1').first().innerText(),
          heading,
          url: page.url().split('#')[1],
        })
      }
    }
    await context.close()
  }
  expect(results).toHaveLength(pages.length * 2)
  expect(errors).toEqual([])
  writeFileSync(
    info.outputPath('all-route-rendering.json'),
    JSON.stringify({ results, errors }, null, 2),
  )
  await info.attach('all-route-rendering.json', {
    body: JSON.stringify({ results, errors }, null, 2),
    contentType: 'application/json',
  })
})
