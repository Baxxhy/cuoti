import { expect, test } from '@playwright/test'

test('英语诊断：误用公式括号的语法短语保留词间空格', async ({ page }, testInfo) => {
  // This isolated rendering contract has no model calls or business writes.
  await page.addInitScript(() =>
    localStorage.setItem('minddimension_access_token', 'rendering-fixture-token'),
  )
  await page.route('**/api/v1/auth/me', (route) =>
    route.fulfill({
      json: { data: { id: 'english-render-only', name: '呈现核验', role: 'student' } },
    }),
  )
  await page.route('**/api/v1/questions/english-render-only', (route) =>
    route.fulfill({
      json: {
        data: {
          id: 'english-render-only',
          subject: '英语',
          grade: '高一',
          question_type: '综合题',
          question_text: 'If I ___ you, I would tell the truth.',
          student_answer: 'am',
          student_steps: [{ id: 's-0', text: '主语是I，所以选am。' }],
          analysis: { final_answer: 'were', reference_steps: ['判断虚拟语气，再选择were。'] },
          diagnosis: {
            first_error_step: 0,
            first_error_text: '主语是I，所以选am。',
            error_type: 'grammar_error',
            root_misconception: '主句 $would tell$ 提示虚拟语气，不能只按主语配现在时。',
            recommended_strategy: '先看would，再选择were。',
            missing_prerequisites: [],
            counterfactual: {},
          },
        },
      },
    }),
  )
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/#/pages/diagnosis/diagnosis?id=english-render-only')
  await expect(page.locator('.summary-title')).toContainText('第 1 步')
  await expect(page.locator('.reason-card')).toContainText('would tell', { useInnerText: true })
  await expect(page.locator('.reason-card .katex')).toHaveCount(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: testInfo.outputPath('english-words.png'), fullPage: true })
})
