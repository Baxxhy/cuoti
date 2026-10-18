import { expect, test, type Page } from '@playwright/test'

const API =
  process.env.ZHIWEI_API_URL ||
  `http://127.0.0.1:${process.env.ZHIWEI_BACKEND_PORT || '8000'}/api/v1`
const teacherAccount = {
  email: process.env.QA_TEACHER_EMAIL || 'teacher@minddimension.local',
  password: process.env.QA_TEACHER_PASSWORD || '123456',
}
async function payload(response: any) {
  expect(response.ok(), `HTTP ${response.status()}`).toBeTruthy()
  const body = await response.json()
  return body.data ?? body
}
async function login(page: Page, email: string, password: string) {
  await page.goto('/#/pages/login/login')
  await page.getByLabel('邮箱', { exact: true }).fill(email)
  await page.getByLabel('密码', { exact: true }).fill(password)
  await page.getByText('登录', { exact: true }).click()
  await expect(page).not.toHaveURL(/login\/login/)
}
function button(scope: any, text: string) {
  return scope.locator('uni-button,button').filter({ hasText: text }).first()
}
async function field(page: Page, label: string, value: string) {
  await page
    .locator('.field')
    .filter({ has: page.getByText(label, { exact: true }) })
    .locator('input,textarea')
    .first()
    .fill(value)
}

test.describe('教师复核的学生可见结果', () => {
  test.skip(process.env.QA_ROLE_TESTS !== '1', '需要初始化的教师账号，写入仅用于独立验收数据')
  test('确认错误、部分正确、退回重做和题目问题均有反馈且完成数准确', async ({
    page,
    browser,
    request,
  }) => {
    test.setTimeout(180_000)
    const email = `qa-review-branches-${Date.now()}@minddimension.local`,
      password = 'ReviewAudit-123'
    const user = await payload(
      await request.post(API + '/auth/register', {
        data: { email, password, name: '复核分支验收', grade: '初一' },
      }),
    )
    const teacher = await payload(
      await request.post(API + '/auth/login', {
        data: teacherAccount,
      }),
    )
    const headers = { Authorization: `Bearer ${teacher.access_token}` }
    const cls = await payload(
      await request.post(API + '/teachers/classes', {
        headers,
        data: { name: `复核分支-${Date.now()}`, grade: '初一', reason: '独立验收' },
      }),
    )
    await payload(
      await request.post(API + `/teachers/classes/${cls.id}/students`, {
        headers,
        data: { email, reason: '独立验收学生' },
      }),
    )
    const q = await payload(
      await request.post(API + '/teachers/questions', {
        headers,
        data: {
          title: `复核分支题-${Date.now()}`,
          question_text: '解方程：2x+3=11',
          standard_answer: 'x=4',
          reference_steps: ['2x=8', 'x=4'],
          subject: '数学',
          grade: '初一',
          question_type: '计算题',
          allow_auto_grade: false,
        },
      }),
    )
    const ctx = await browser.newContext({
      ignoreHTTPSErrors: process.env.QA_PREVIEW_HTTPS === '1',
      viewport: { width: 390, height: 844 },
      isMobile: true,
      hasTouch: true,
    })
    const pupil = await ctx.newPage()
    await login(pupil, email, password)
    await login(page, teacherAccount.email, teacherAccount.password)
    for (const [label, conclusion, state] of [
      ['确认错误', 'confirmed_incorrect', 'completed'],
      ['部分正确', 'partially_correct', 'completed'],
      ['退回重做', 'resubmit', 'pending'],
      ['题目有问题', 'question_issue', 'question_issue'],
    ]) {
      const title = `验收-${label}-${Date.now()}`
      const assignment = await payload(
        await request.post(API + '/teachers/assignments', {
          headers,
          data: {
            title,
            class_id: cls.id,
            question_id: q.question.id,
            settings: {
              allow_auto_grade: false,
              require_teacher_review: true,
              count_mastery: false,
            },
          },
        }),
      )
      await pupil.goto('/#/pages/index/index')
      await pupil.getByText('查看任务', { exact: true }).click()
      const card = pupil.locator('.assignment-card').filter({ hasText: title })
      if ((await card.locator('.assignment-header').getAttribute('aria-expanded')) !== 'true')
        await card.locator('.assignment-header').click()
      await card.locator('.written-answer textarea').fill('x=7')
      await button(card, '提交作答').click()
      await expect(card).toContainText('等待教师核对')
      const before = await payload(await request.get(API + '/teachers/assignments', { headers }))
      expect(before.find((x: any) => x.id === assignment.id).completed_count).toBe(0)
      const tasks = await payload(
        await request.get(API + `/teachers/reviews?student_id=${user.id}`, { headers }),
      )
      const task = tasks.find((x: any) => x.question_id === q.question.id)
      expect(task).toBeTruthy()
      await page.goto(`/#/pages/teacher/review-detail?id=${task.id}`)
      await page.getByText(label, { exact: true }).click()
      if (conclusion === 'partially_correct') await field(page, '得分', '40')
      if (['confirmed_incorrect', 'partially_correct'].includes(conclusion))
        await field(page, '第一个关键错误', '移项没有变号')
      await field(page, '复核理由（必填）', '根据本题等式关系核对作答')
      await field(page, '给学生的提示', '检查移项时常数项的符号')
      await field(page, '下一步学习任务', '再做一道移项练习')
      const saved = page.waitForResponse(
        (r) => r.url().endsWith('/decision') && r.request().method() === 'POST',
      )
      await button(page, '确认结论').click()
      expect((await saved).ok()).toBeTruthy()
      await pupil.reload()
      if ((await card.locator('.assignment-header').getAttribute('aria-expanded')) !== 'true')
        await card.locator('.assignment-header').click()
      await expect(card.locator('.teacher-feedback')).toContainText('检查移项时常数项的符号')
      await expect(card.locator('.teacher-feedback')).toContainText('再做一道移项练习')
      const rows = await payload(
        await request.get(API + '/students/assignments', {
          headers: { Authorization: `Bearer ${user.access_token}` },
        }),
      )
      const row = rows.find((x: any) => x.assignment.id === assignment.id)
      expect(row.student_assignment.status).toBe(state)
      expect(row.teacher_feedback.conclusion).toBe(conclusion)
      if (state === 'pending') await expect(button(card, '提交作答')).toBeVisible()
      if (state === 'question_issue') await expect(card).toContainText('题目正在核对')
      const after = await payload(await request.get(API + '/teachers/assignments', { headers }))
      expect(after.find((x: any) => x.id === assignment.id).completed_count).toBe(
        state === 'completed' ? 1 : 0,
      )
    }
    await ctx.close()
  })
})

test('真实账号之间不能访问错题、试卷或教师权限，注册不能提升身份', async ({ request }) => {
  const register = async (label: string) =>
    payload(
      await request.post(API + '/auth/register', {
        data: {
          email: `qa-isolation-${label}-${Date.now()}@minddimension.local`,
          password: 'Isolated-123',
          name: label,
          grade: '初一',
          role: 'admin',
        },
      }),
    )
  const first = await register('第一学生'),
    second = await register('第二学生')
  expect(first.role).toBe('student')
  expect(second.role).toBe('student')
  const owner = { Authorization: `Bearer ${first.access_token}` },
    other = { Authorization: `Bearer ${second.access_token}` }
  const q = await payload(
    await request.post(API + '/questions/manual', {
      headers: owner,
      data: { question_text: '私有验收题：2x+3=11', subject: '数学', grade: '初一' },
    }),
  )
  expect((await request.get(API + '/questions/' + q.id, { headers: other })).status()).toBe(404)
  expect((await request.delete(API + '/questions/' + q.id, { headers: other })).status()).toBe(404)
  const paper = await payload(
    await request.post(API + '/papers', {
      headers: owner,
      data: { title: '隔离验收试卷', question_ids: [q.id] },
    }),
  )
  for (const response of [
    await request.get(API + '/papers/' + paper.id, { headers: other }),
    await request.patch(API + '/papers/' + paper.id, {
      headers: other,
      data: { title: '不应修改' },
    }),
    await request.post(API + '/papers/' + paper.id + '/export', {
      headers: other,
      data: { type: 'question_pdf' },
    }),
    await request.get(API + '/teachers/dashboard', { headers: other }),
    await request.get(API + '/admin/workbench', { headers: other }),
  ])
    expect([403, 404]).toContain(response.status())
  expect(
    (await payload(await request.get(API + '/papers/' + paper.id, { headers: owner }))).title,
  ).toBe('隔离验收试卷')
})
