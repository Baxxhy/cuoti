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
  await expect(page.locator('.bank-question').first()).toContainText('练习验收题库')
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
