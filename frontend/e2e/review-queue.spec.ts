import { expect, test } from '@playwright/test'

test('多题复习：缺参考的题不挡住下一题，草稿与位置恢复且不记完成', async ({
  page,
  request,
}, testInfo) => {
  test.skip(!process.env.QA_REVIEW_QUEUE_TOKEN, '需要隔离仓颉多题复习样本')
  const token = process.env.QA_REVIEW_QUEUE_TOKEN!,
    first = process.env.QA_REVIEW_QUEUE_FIRST!,
    second = process.env.QA_REVIEW_QUEUE_SECOND!
  await page.addInitScript(
    (value) => localStorage.setItem('minddimension_access_token', value),
    token,
  )
  await page.setViewportSize({ width: 390, height: 844 })
  let attempts = 0,
    grades = 0
  page.on('request', (request) => {
    if (request.method() !== 'POST') return
    if (/\/reviews\/[^/]+\/attempt$/.test(request.url())) attempts++
    if (/\/reviews\/[^/]+\/grade$/.test(request.url())) grades++
  })
  await page.goto('/#/pages/review/review')
  await expect(page.locator('.review-question')).toContainText('x+2=5')
  const input = page.locator('.written-answer textarea').first()
  await input.fill('还需要想一想')
  await page.getByRole('button', { name: '提交并判定', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('标准答案')
  await page.getByRole('button', { name: '下一题', exact: true }).click()
  await expect(page.locator('.review-question')).toContainText('7+5')
  await expect(input).toHaveValue('')
  await input.fill('12')
  await page.getByRole('button', { name: '上一题', exact: true }).click()
  await expect(input).toHaveValue('还需要想一想')
  await page.getByRole('button', { name: '下一题', exact: true }).click()
  await page.reload()
  await expect(page.locator('.review-question')).toContainText('7+5')
  await expect(input).toHaveValue('12')
  await expect(page.getByRole('button', { name: '下一题', exact: true })).toHaveAttribute(
    'aria-disabled',
    'true',
  )
  await page.screenshot({ path: testInfo.outputPath('review-queue.png'), fullPage: true })
  expect(attempts).toBe(1)
  expect(grades).toBe(0)
  const headers = { Authorization: `Bearer ${token}` }
  const today = await request.get(`${process.env.ZHIWEI_API_URL}/reviews/today`, { headers })
  expect(today.ok()).toBe(true)
  const plans = (await today.json()).data
  expect(plans.map((row: any) => row.id)).toEqual([first, second])
  expect(plans.every((row: any) => row.status === 'pending' && row.pending_attempt === null)).toBe(
    true,
  )
  const history = await request.get(`${process.env.ZHIWEI_API_URL}/reviews/history`, { headers })
  expect((await history.json()).data).toEqual([])
  await page.goto(`/#/pages/review/review?plan=${first}`)
  // A fresh entry is required: changing only the current H5 hash query does not recreate a uni-app page.
  await page.reload()
  await expect(page.locator('.review-question')).toContainText('x+2=5')
  await expect(input).toHaveValue('还需要想一想')
})

test('多题复习：本地缓存失效时本页仍保留草稿，窄屏放大文字可切题', async ({ page }, testInfo) => {
  test.skip(!process.env.QA_REVIEW_QUEUE_TOKEN, '需要隔离仓颉多题复习样本')
  await page.addInitScript((token) => {
    localStorage.setItem('minddimension_access_token', token)
    const set = Storage.prototype.setItem
    Storage.prototype.setItem = function (key, value) {
      if (String(key).startsWith('minddimension_task_'))
        throw new DOMException('Local storage unavailable', 'QuotaExceededError')
      return set.call(this, key, value)
    }
  }, process.env.QA_REVIEW_QUEUE_TOKEN!)
  await page.goto('/#/pages/review/review')
  const input = page.locator('.written-answer textarea').first()
  await input.fill('本页保留的第一题草稿')
  await page.getByRole('button', { name: '下一题', exact: true }).click()
  await input.fill('本页保留的第二题草稿')
  await page.getByRole('button', { name: '上一题', exact: true }).click()
  await expect(input).toHaveValue('本页保留的第一题草稿')
  await expect(
    page.getByText('本机暂时无法保存草稿，请保持此页打开后提交。', { exact: true }),
  ).toBeVisible()
  for (const width of [360, 390, 430]) {
    await page.setViewportSize({ width, height: 700 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  }
  await page.setViewportSize({ width: 360, height: 700 })
  const enlargeText = () =>
    page.evaluate(() => {
      const values = [...document.querySelectorAll<HTMLElement>('uni-text,uni-button,textarea')]
        .filter((el) => el.getClientRects().length && !el.closest('uni-icons'))
        .map((el) => {
          el.dataset.qaFontSize ||= getComputedStyle(el).fontSize
          return [el, parseFloat(el.dataset.qaFontSize)] as const
        })
      for (const [el, size] of values) {
        el.style.fontSize = `${size * 2}px`
        el.style.lineHeight = '1.5'
      }
    })
  await enlargeText()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.getByRole('button', { name: '下一题', exact: true }).focus()
  await page.keyboard.press('Enter')
  await expect(input).toHaveValue('本页保留的第二题草稿')
  await enlargeText()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: testInfo.outputPath('review-queue-large.png'), fullPage: true })
})
