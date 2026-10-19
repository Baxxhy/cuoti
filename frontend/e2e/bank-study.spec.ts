import { expect, test, type Page } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  test.skip(!process.env.QA_STUDY_SOURCE, '需要独立题库与考试样本')
  await page.goto('/#/pages/login/login')
  await page.getByLabel('邮箱', { exact: true }).fill(process.env.QA_STUDY_EMAIL!)
  await page.getByLabel('密码', { exact: true }).fill(process.env.QA_STUDY_PASSWORD!)
  await page.getByText('登录', { exact: true }).click()
  await expect(page).toHaveURL(/pages\/index\/index/)
})
async function bank(page: Page, mode: string) {
  await page.goto(
    `/#/pages/bank/bank?mode=${mode}&subject=${encodeURIComponent('数学')}&source_id=${process.env.QA_STUDY_SOURCE}`,
  )
  await expect(page.locator('.bank-count')).toHaveText('6 道可练习题目')
}
async function turnIn(page: Page) {
  await page.getByRole('button', { name: '交卷并查看结果', exact: true }).click()
  await page.getByText('交卷', { exact: true }).click()
  await expect(page.locator('.result-summary')).toBeVisible({ timeout: 30000 })
}
test('题库独立于错题：真实来源、作答自动保存、刷新恢复、交卷后显示答案', async ({ page }, info) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await bank(page, 'practice')
  await expect(page.locator('.bank-question')).toHaveCount(6)
  await expect(page.locator('.bank-question').first()).not.toContainText('练习验收题库')
  await expect(page.locator('.bank-question').first()).not.toContainText('来源')
  await expect(page.getByText('全部来源', { exact: true })).toHaveCount(0)
  await page.locator('.bank-question').first().click()
  await expect(page).toHaveURL(/pages\/study-session\/study-session/)
  await expect(page.locator('.answer-review')).toHaveCount(0)
  // A failed autosave must retain the student's local draft across a refresh.
  await page.route('**/api/v1/study-sessions/*', (route) =>
    route.request().method() === 'PATCH' ? route.abort('failed') : route.continue(),
  )
  await page.locator('.answer-options uni-button, .answer-options button').first().click()
  await expect(page.getByRole('alert')).toBeVisible()
  await page.unroute('**/api/v1/study-sessions/*')
  await page.reload()
  await expect(
    page.locator('.answer-options uni-button, .answer-options button').first(),
  ).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByRole('status')).toHaveText('作答已保存')
  await page.reload()
  await expect(
    page.locator('.answer-options uni-button, .answer-options button').first(),
  ).toHaveAttribute('aria-pressed', 'true')
  await turnIn(page)
  await expect(page.locator('.result-score > uni-text').first()).toHaveText('5')
  await expect(page.locator('.answer-review')).toHaveCount(1)
  await expect(page.locator('.answer-review')).toContainText('参考答案')
  await page.screenshot({ path: info.outputPath('practice-result.png'), fullPage: true })
  await page.reload()
  await expect(page.locator('.result-title')).toHaveText('练习完成')
  await bank(page, 'practice')
  await expect(page.locator('.session-record').first()).toContainText('5 / 5 分')
})
test('模拟考试：抽取题库、计时、逐题作答与答题卡、交卷、错题自选收录', async ({ page }, info) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await bank(page, 'exam')
  await page.getByRole('button', { name: '开始模拟考试', exact: true }).click()
  await expect(page.getByRole('timer')).toBeVisible()
  await expect(page.locator('.question-grid uni-button, .question-grid button')).toHaveCount(5)
  for (let i = 0; i < 5; i++) {
    await page.getByRole('button', { name: `第${i + 1}题`, exact: true }).click()
    await page
      .locator('.answer-options uni-button, .answer-options button')
      .nth(i === 0 ? 1 : 0)
      .click()
  }
  await expect(page.getByRole('status')).toHaveText('作答已保存')
  await page.reload()
  await expect(
    page.locator('.question-grid uni-button.answered, .question-grid button.answered'),
  ).toHaveCount(5)
  await expect(page.getByRole('timer')).toHaveText(/\d+:\d+/)
  await page.screenshot({ path: info.outputPath('exam-answering.png'), fullPage: true })
  await turnIn(page)
  await expect(page.locator('.result-score > uni-text').first()).toHaveText('20')
  await expect(page.locator('.answer-review')).toHaveCount(5)
  await page.getByRole('button', { name: '加入错题本', exact: true }).click()
  await expect(page.getByRole('button', { name: '已加入错题本', exact: true })).toBeVisible()
  await page.screenshot({ path: info.outputPath('exam-result.png'), fullPage: true })
  await bank(page, 'exam')
  await expect(page.locator('.session-record').first()).toContainText('20 / 25 分')
  for (const width of [360, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 })
    await expect(page.locator('.exam-setup')).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.screenshot({ path: info.outputPath(`exam-setup-${width}.png`), fullPage: true })
  }
})

test('化学题干与选项中的短公式连续排版，解析保留独立公式', async ({ page }, info) => {
  test.skip(!process.env.QA_STUDY_CHEM_SOURCE, '需要化学排版样本')
  await page.goto(`/#/pages/bank/bank?source_id=${process.env.QA_STUDY_CHEM_SOURCE}`)
  await expect(page.locator('.bank-question')).toHaveCount(1)
  await expect(page.locator('.bank-question .katex-display')).toHaveCount(0)
  await page.locator('.bank-question').click()
  const options = page.locator('.answer-options uni-button, .answer-options button')
  await expect(options).toHaveCount(4)
  await expect(page.locator('.question-stem .katex')).toHaveCount(2)
  expect(
    await page.locator('.question-stem').evaluate((element) => {
      const copy = element.cloneNode(true) as HTMLElement
      copy.querySelectorAll('.katex').forEach((node) => node.remove())
      return /\\[A-Za-z]+/.test(copy.textContent || '')
    }),
  ).toBe(false)
  for (const width of [360, 390, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 })
    await expect(
      page.locator('.question-stem .katex-display, .answer-options .katex-display'),
    ).toHaveCount(0)
    await expect(options.nth(0)).toContainText('杂化')
    expect(
      await options
        .nth(0)
        .locator('.math-text')
        .evaluate((el) => el.getBoundingClientRect().height),
    ).toBeLessThan(60)
    expect(
      await options
        .nth(2)
        .locator('.math-text')
        .evaluate((el) => el.getBoundingClientRect().height),
    ).toBeLessThan(85)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.screenshot({
      path: info.outputPath(`chemical-options-${width}.png`),
      fullPage: true,
    })
  }
  await options.nth(3).click()
  await expect(page.getByRole('status')).toHaveText('作答已保存')
  await turnIn(page)
  await expect(page.locator('.review-option .katex-display')).toHaveCount(0)
  await expect(page.locator('.reference-solution .katex-display')).toHaveCount(1)
  await expect(page.locator('.result-score > uni-text').first()).toHaveText('5')
})

test('停用题目不显示损坏原文，已有练习交卷时排除该题分值', async ({ page }) => {
  test.skip(!process.env.QA_STUDY_BLOCKED_SESSION, '需要停用题目样本')
  await page.goto(`/#/pages/study-session/study-session?id=${process.env.QA_STUDY_BLOCKED_SESSION}`)
  await expect(page.locator('.question-workspace .unavailable-note')).toContainText(
    '此题已暂停使用',
  )
  await expect(page.locator('.answer-options')).toHaveCount(0)
  await expect(page.getByText('不应展示的坏公式', { exact: false })).toHaveCount(0)
  await expect(page.locator('.math-unparsed, .katex-error')).toHaveCount(0)
  await turnIn(page)
  await expect(page.locator('.result-summary')).toContainText('1 题已暂停使用，未计分')
  await expect(page.locator('.result-score')).toHaveCount(0)
  await expect(page.locator('.result-title')).toHaveText('本次练习已暂停')
  await expect(page.locator('.answer-review .unavailable-note')).toHaveText('此题已暂停使用')
  await expect(page.locator('.answer-review .math-text')).toHaveCount(0)
  await expect(page.getByRole('button', { name: '加入错题本', exact: true })).toHaveCount(0)
  await page.getByRole('button', { name: '返回题库', exact: true }).click()
  await expect(page.locator('.record-status').filter({ hasText: '已暂停' }).first()).toBeVisible()
  await expect(page.locator('.session-history')).not.toContainText('0 / 0 分')
})
