import { expect, test, type Page, type APIRequestContext } from '@playwright/test'

const API =
  process.env.ZHIWEI_API_URL ||
  `http://127.0.0.1:${process.env.ZHIWEI_BACKEND_PORT || '8000'}/api/v1`
const roleTests = process.env.QA_ROLE_TESTS === '1'
const roleAccount = (role: string) => ({
  email: process.env[`QA_${role.toUpperCase()}_EMAIL`] || `${role}@minddimension.local`,
  password: process.env[`QA_${role.toUpperCase()}_PASSWORD`] || '123456',
})

async function data(response: any) {
  expect(response.ok(), `HTTP ${response.status()}`).toBeTruthy()
  const body = await response.json()
  return body.data ?? body
}
async function student(request: APIRequestContext) {
  const credentials = {
    email: `ui-audit-${Date.now()}-${Math.random().toString(36).slice(2)}@minddimension.local`,
    password: 'UiAudit-123456',
  }
  const user = await data(
    await request.post(API + '/auth/register', {
      data: { ...credentials, name: '界面验收学生', grade: '高一' },
    }),
  )
  return { ...credentials, user, headers: { Authorization: `Bearer ${user.access_token}` } }
}
async function login(page: Page, credentials: { email: string; password: string }) {
  await page.goto('/#/pages/login/login')
  await page.getByLabel('邮箱', { exact: true }).fill(credentials.email)
  await page.getByLabel('密码', { exact: true }).fill(credentials.password)
  await page.getByText('登录', { exact: true }).click()
  await expect(page.getByText('欢迎回来', { exact: true })).toHaveCount(0)
}
async function manual(request: APIRequestContext, account: any, text = '界面验收：解方程2x+3=11') {
  const created = await data(
    await request.post(API + '/questions/manual', {
      headers: account.headers,
      data: {
        question_text: text,
        student_answer: 'x=7',
        student_steps: ['2x=11+3', 'x=7'],
        subject: '数学',
        grade: '高一',
      },
    }),
  )
  return data(await request.get(API + '/questions/' + created.id, { headers: account.headers }))
}

function button(page: Page, text: string) {
  return page.locator('uni-button,button').filter({ hasText: text }).first()
}

test('讲回、练习和复习的文字输入实际渲染且提交内容正确', async ({ page, request }) => {
  // Controlled public tasks isolate component rendering from remote AI availability.
  // Real model and database flows are separately recorded in the QA report.
  const account = await student(request)
  await login(page, account)
  const warnings: string[] = []
  page.on('console', (message) => {
    if (message.text().includes('Failed to resolve component')) warnings.push(message.text())
  })
  const session = {
    id: 'ui-input-session',
    stage: 'teach_back',
    status: 'active',
    visualization_available: true,
    knowledge_title: '等式的性质',
    activity: {
      id: 'teach-back',
      type: 'teach_back',
      question: '移项为什么变号？',
      attempt: 1,
      max_attempts: 2,
      options: [],
      keywords: [],
    },
  }
  await page.route('**/tutor/sessions/ui-input-session', (route) =>
    route.fulfill({ json: { data: session } }),
  )
  let submitted: any
  await page.route('**/tutor/sessions/ui-input-session/activity/answer', async (route) => {
    submitted = route.request().postDataJSON()
    await route.fulfill({ json: { data: { ...session, stage: 'finished', activity: null } } })
  })
  await page.goto('/#/pages/tutor/tutor?id=ui-input-session')
  await page.route('**/tutor/sessions/ui-input-session/visualization', (route) =>
    route.fulfill({
      json: {
        data: {
          question: { question_text: '解方程：2x+3=11' },
          spec: {
            type: 'equation_balance',
            title: '等式天平',
            parameters: {},
            interactive_variables: [
              { name: 'delta', label: '两边同时减去', min: -5, max: 5, step: 1, value: 3 },
            ],
            student_task: '观察天平',
            expected_observation: '两边仍相等',
          },
        },
      },
    }),
  )
  await button(page, '互动演示').click()
  await expect(page.locator('[data-visualization-type="equation_balance"]')).toBeVisible()
  const track = page.locator('.uni-slider-handle-wrapper')
  await track.tap({ position: { x: 5, y: 1 } })
  await expect(page.locator('.control b')).not.toHaveText('3')
  await page.locator('.field-textarea textarea').fill('两边同时减去3仍相等。')
  await button(page, '保存并继续').click()
  await expect(page).toHaveURL(/tutor\/tutor/)
  await expect(page.locator('.answer-area textarea').first()).toBeVisible()
  await expect(button(page, '讲完了')).toHaveAttribute('disabled', 'true')
  await page.locator('.answer-area textarea').first().fill('等式两边同时减去同一项，所以移项变号。')
  await button(page, '讲完了').click()
  await expect(page.locator('.finish-card')).toBeVisible()
  expect(submitted.answer).toBe('等式两边同时减去同一项，所以移项变号。')

  await page.route('**/practice/recommend', (route) =>
    route.fulfill({
      json: {
        data: {
          question_id: 'ui-practice-question',
          stem: '解方程：2x+3=11',
          subject: '数学',
          grade: '初一',
          question_type: '解答题',
          options: [],
        },
      },
    }),
  )
  await page.route('**/practice/attempt', async (route) => {
    submitted = route.request().postDataJSON()
    await route.fulfill({
      json: {
        data: { correct: true, can_update_learning: true, feedback: '回答正确', answer: 'x=4' },
      },
    })
  })
  await page.goto('/#/pages/practice/practice?id=ui-mistake')
  await expect(page.locator('.written-answer textarea').first()).toBeVisible()
  await page.locator('.written-answer textarea').first().fill('x=4')
  await button(page, '提交答案').click()
  await expect(page.locator('.result-card')).toContainText('回答正确')
  expect(submitted.student_answer).toBe('x=4')

  await page.route('**/reviews/today', (route) =>
    route.fulfill({
      json: {
        data: [
          {
            id: 'ui-review-plan',
            question: {
              id: 'ui-review-question',
              question_text: '解方程：2x+3=11',
              subject: '数学',
              grade: '初一',
              options: [],
            },
          },
        ],
      },
    }),
  )
  await page.route('**/reviews/ui-review-plan/attempt', async (route) => {
    submitted = route.request().postDataJSON()
    await route.fulfill({
      json: {
        data: {
          attempt_id: 'ui-review-attempt',
          correct: true,
          can_update_learning: true,
          feedback: '回答正确',
          expected_answer: 'x=4',
        },
      },
    })
  })
  await page.goto('/#/pages/review/review')
  await expect(page.locator('.written-answer textarea').first()).toBeVisible()
  await page.locator('.written-answer textarea').first().fill('x=4')
  await button(page, '提交并判定').click()
  await expect(page.locator('.grade-grid')).toBeVisible()
  expect(submitted.answer).toBe('x=4')
  expect(warnings).toEqual([])
})
async function field(page: Page, label: string, value: string) {
  await page
    .locator('.field')
    .filter({ has: page.getByText(label, { exact: true }) })
    .locator('input,textarea')
    .first()
    .fill(value)
}
async function choose(page: Page, control: any, label: string) {
  await control.click()
  const mobile = page.locator('.uni-picker-custom.uni-picker-toggle')
  if (await page.evaluate(() => innerWidth < 768)) {
    await expect(mobile).toBeVisible()
    const target = mobile
      .locator('.uni-picker-view-content .uni-picker-item')
      .filter({ hasText: new RegExp(`^${label}$`) })
    await expect(target).toBeVisible()
    // The wheel animates into position; wait for its stable box before a real touch.
    const wheel = mobile.locator('.uni-picker-view-group')
    let previousY: number | undefined,
      stable = 0
    await expect
      .poll(async () => {
        const bounds = await wheel.boundingBox()
        if (bounds && previousY !== undefined && Math.abs(bounds.y - previousY) < 0.5) stable += 1
        else stable = 0
        previousY = bounds?.y
        return stable
      })
      .toBeGreaterThanOrEqual(2)
    const targetBox = await target.boundingBox(),
      wheelBox = await wheel.boundingBox()
    await wheel.tap({
      position: { x: wheelBox!.width / 2, y: targetBox!.y - wheelBox!.y + targetBox!.height / 2 },
    })
    await expect(mobile.locator('.uni-picker-select .selected')).toHaveText(label)
    await mobile.locator('.uni-picker-action-confirm').tap()
  } else {
    await page
      .locator('.uni-picker-item:visible')
      .filter({ hasText: new RegExp(`^${label}$`) })
      .click()
  }
  await expect(control).toContainText(label)
}

test('错题筛选、搜索、详情折叠、修改与取消归档均可操作', async ({ page, request }) => {
  const account = await student(request)
  const q = await manual(request, account, '界面验收方程：2x+3=11')
  await login(page, account)
  await page.getByRole('button', { name: '错题', exact: true }).click()
  await expect(page.getByText(q.question_text, { exact: true })).toBeVisible()
  await page.getByText('物理', { exact: true }).click()
  await expect(page.getByText('没有符合条件的错题', { exact: true })).toBeVisible()
  await page.getByText('数学', { exact: true }).click()
  await expect(page.getByText(q.question_text, { exact: true })).toBeVisible()
  await page.locator('.inline-search input').fill('方程')
  await button(page, '搜索').click()
  await expect(page.locator('.problem-card')).toHaveCount(1)
  await page.locator('.problem-card').click()
  await page.getByRole('button', { name: '记录', exact: true }).click()
  await page.getByText('我的完整步骤', { exact: true }).click()
  await expect(page.locator('.fold-body')).toContainText('2x=11+3')
  await page.getByText('参考步骤', { exact: true }).click()
  await expect(page.locator('.fold-body')).not.toContainText('2x=11+3')
  await button(page, '修改录入内容').click()
  await expect(page.locator('.question-editor textarea')).toHaveValue(q.question_text)
  await page.locator('.question-editor textarea').fill('界面验收方程已修改：2x+3=11')
  await button(page, '保存修改').click()
  await expect(page).toHaveURL(/pages\/detail\/detail/)
  await expect(page.getByText('界面验收方程已修改：2x+3=11', { exact: true })).toBeVisible()
  await page.locator('.header-extra').click()
  await page.getByText('移出错题本', { exact: true }).click()
  await page.locator('.uni-modal').getByText('取消', { exact: true }).click()
  await expect(page.getByText('界面验收方程已修改：2x+3=11', { exact: true })).toBeVisible()
  const saved = await data(
    await request.get(API + '/questions/' + q.id, { headers: account.headers }),
  )
  expect(saved.status).not.toBe('archived')
})

test('组卷高级筛选、选择、保存、排序和三类导出真实生效', async ({ page, request }) => {
  const account = await student(request)
  await manual(request, account, '组卷验收题一：2x+3=11')
  await manual(request, account, '组卷验收题二：x+5=9')
  await login(page, account)
  await page.getByRole('button', { name: '学习', exact: true }).click()
  await page.getByRole('button', { name: '考前组卷', exact: true }).click()
  await expect(page.locator('.advanced-filters')).not.toBeVisible()
  await page.getByText('更多筛选条件', { exact: true }).click()
  await expect(page.locator('.advanced-filters')).toBeVisible()
  await field(page, '知识点', '不存在的知识点')
  await button(page, '按条件筛选题目').click()
  await expect(page.locator('.candidate')).toHaveCount(0)
  await field(page, '知识点', '')
  await button(page, '按条件筛选题目').click()
  await expect(page.locator('.candidate')).toHaveCount(2)
  await page.getByText('全选', { exact: true }).click()
  await expect(page.locator('.candidate.selected')).toHaveCount(2)
  await button(page, '创建试卷').click()
  await expect(page.locator('.paper-editor')).toBeVisible()
  await page.locator('.editor-title input').fill('前端验收试卷')
  await page.locator('.paper-item .score-edit input').nth(0).fill('15')
  const before = await page.locator('.paper-item .list-main b').nth(0).innerText()
  await page.locator('.paper-item .sort').nth(0).getByText('↓', { exact: true }).click()
  expect(await page.locator('.paper-item .list-main b').nth(1).innerText()).toBe(before)
  const savedResponse = page.waitForResponse(
    (response) => response.url().includes('/papers/') && response.request().method() === 'PATCH',
  )
  await button(page, '保存名称、排序与分值').click()
  expect((await savedResponse).ok()).toBe(true)
  await expect(button(page, '保存名称、排序与分值')).not.toHaveAttribute('disabled', 'true')
  await expect(page.locator('.total-score')).toContainText('25')
  for (const label of ['题目 PDF', '答案 PDF', '学习表格']) {
    await expect(button(page, label)).not.toHaveAttribute('disabled', 'true')
    const exported = page.waitForResponse(
      (response) => response.url().endsWith('/export') && response.request().method() === 'POST',
    )
    await button(page, label).click()
    expect((await exported).ok()).toBe(true)
    await expect(page.locator('.download-row')).toHaveCount(
      ['题目 PDF', '答案 PDF', '学习表格'].indexOf(label) + 1,
    )
  }
  // Exercise the real open control through the same origin as the compiled page.
  const openedFile = page.context().waitForEvent('response', {
    predicate: (response) => new URL(response.url()).pathname.startsWith('/reports/'),
  })
  await page.locator('.download-row').filter({ hasText: '题目 PDF' }).click()
  const openedResponse = await openedFile
  expect(openedResponse.ok()).toBeTruthy()
  expect(new URL(openedResponse.url()).origin).toBe(new URL(page.url()).origin)
  for (const popup of page.context().pages()) if (popup !== page) await popup.close()
  const papers = await data(await request.get(API + '/papers', { headers: account.headers }))
  const paper = await data(
    await request.get(API + '/papers/' + papers[0].id, { headers: account.headers }),
  )
  expect(paper.title).toBe('前端验收试卷')
  expect(paper.items.reduce((sum: number, item: any) => sum + item.score, 0)).toBe(25)
  expect(paper.exports).toHaveLength(3)
  for (const file of paper.exports) {
    const download = await request.get(new URL(file.url, API).href)
    expect(download.ok()).toBeTruthy()
    expect((await download.body()).length).toBeGreaterThan(100)
  }
  await page.getByText('删除', { exact: true }).click()
  await page.locator('.uni-modal').getByText('取消', { exact: true }).click()
  await expect(page.locator('.paper-editor')).toBeVisible()
})

test('页面加载失败后重试恢复，颜色和操作不依赖旧数据', async ({ page, request }) => {
  const account = await student(request)
  await login(page, account)
  let fail = true
  await page.route('**/api/v1/questions', (route) =>
    fail
      ? route.fulfill({
          status: 503,
          contentType: 'application/json',
          body: JSON.stringify({ detail: '验收网络失败' }),
        })
      : route.continue(),
  )
  await page.getByRole('button', { name: '错题', exact: true }).click()
  await expect(page.locator('.state-panel')).toContainText('验收网络失败')
  fail = false
  await button(page, '重新加载').click()
  await expect(page.getByText('还没有错题', { exact: true })).toBeVisible()
  await page.unroute('**/api/v1/questions')
})

test.describe('角色页面操作', () => {
  test.skip(!roleTests, '显式 QA_ROLE_TESTS=1 启用，依赖隔离验收教师、家长、管理员账号')
  test.use({
    viewport: { width: 390, height: 844 },
    screen: { width: 390, height: 844 },
    isMobile: true,
    hasTouch: true,
  })

  test('教师和家长的个人中心入口可见、可点击且可返回', async ({ page }) => {
    for (const role of ['teacher', 'guardian']) {
      await login(page, roleAccount(role))
      const entry = page.getByRole('button', { name: '个人中心', exact: true })
      await expect(entry).toBeVisible()
      const iconColor = await entry
        .locator('.uni-icons')
        .evaluate((el) => getComputedStyle(el).color)
      expect(iconColor).not.toBe('rgb(255, 255, 255)')
      await entry.click()
      await expect(
        page.getByText(role === 'teacher' ? '返回教师中心' : '返回家长中心', { exact: true }),
      ).toBeVisible()
      await button(page, '退出登录').click()
      await expect(page.getByText('欢迎回来', { exact: true })).toBeVisible()
    }
  })

  test('学生授权、家长读取报告、学生撤回及家长解除后权限同步', async ({
    page,
    request,
    browser,
  }) => {
    const account = await student(request)
    await manual(request, account)
    const guardian = roleAccount('guardian')
    await login(page, account)
    await page.getByRole('button', { name: '我的', exact: true }).click()
    await page.getByText('家长查看权限', { exact: true }).click()
    await expect(page.getByText('还没有家长可以查看你的报告。', { exact: true })).toBeVisible()
    const grant = async () => {
      await page.locator('.grant-form input').fill(guardian.email)
      await button(page, '核对并授权').click()
      await page.getByText('确认授权', { exact: true }).click()
      await expect(page.locator('.access-row')).toHaveCount(1)
    }
    await grant()
    const ctx = await browser.newContext({
      viewport: { width: 360, height: 800 },
      isMobile: true,
      hasTouch: true,
      ignoreHTTPSErrors: process.env.QA_PREVIEW_HTTPS === '1',
    })
    try {
      const parent = await ctx.newPage()
      await login(parent, guardian)
      await parent
        .getByRole('button', { name: '查看界面验收学生的学习报告', exact: true })
        .press('Enter')
      await expect(parent.locator('.report-profile')).toContainText('界面验收学生的学习报告')
      await expect(parent.locator('.report-stats').locator('b').first()).toHaveText('1')
      expect(await parent.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
        true,
      )
      await button(page, '解除').click()
      await page.getByText('取消', { exact: true }).click()
      await expect(page.locator('.access-row')).toHaveCount(1)
      await button(page, '解除').click()
      await page.getByText('确认解除', { exact: true }).click()
      await expect(page.locator('.access-row')).toHaveCount(0)
      await button(parent, '刷新报告').click()
      await expect(parent.locator('.state-panel')).toContainText('当前已无权查看这份报告')
      await expect(parent.locator('.report-profile')).toHaveCount(0)
      await button(parent, '返回家长中心').click()
      await expect(
        parent.getByRole('button', { name: '查看界面验收学生的学习报告', exact: true }),
      ).toHaveCount(0)
      await grant()
      await parent.reload()
      const card = parent.locator('.student-card').filter({ hasText: '界面验收学生' })
      await button(card, '解除关联').click()
      await parent.getByText('确认解除', { exact: true }).click()
      await expect(card).toHaveCount(0)
      await page.reload()
      await expect(page.locator('.access-row')).toHaveCount(0)
      const response = await request.get(API + `/guardians/students/${account.user.id}/overview`, {
        headers: {
          Authorization: `Bearer ${(await data(await request.post(API + '/auth/login', { data: guardian }))).access_token}`,
        },
      })
      expect(response.status()).toBe(403)
    } finally {
      await ctx.close()
    }
  })

  test('多项作业只展开一项，切换保留文字，提交后仍可查看状态', async ({ page, request }) => {
    const account = await student(request)
    const teacher = await data(
      await request.post(API + '/auth/login', { data: roleAccount('teacher') }),
    )
    const headers = { Authorization: `Bearer ${teacher.access_token}` }
    const cls = await data(
      await request.post(API + '/teachers/classes', {
        headers,
        data: { name: `简洁作业班-${Date.now()}`, grade: '初一' },
      }),
    )
    await data(
      await request.post(API + `/teachers/classes/${cls.id}/students`, {
        headers,
        data: { email: account.email },
      }),
    )
    const question = await data(
      await request.post(API + '/teachers/questions', {
        headers,
        data: {
          title: `简洁作业题-${Date.now()}`,
          question_text: '解方程：2x+3=11',
          standard_answer: 'x=4',
          reference_steps: ['2x=8', 'x=4'],
          subject: '数学',
          grade: '初一',
          allow_auto_grade: false,
        },
      }),
    )
    for (const title of ['第一项：移项练习', '第二项：等式练习']) {
      await data(
        await request.post(API + '/teachers/assignments', {
          headers,
          data: {
            title,
            class_id: cls.id,
            question_id: question.question.id,
            settings: {
              allow_auto_grade: false,
              require_teacher_review: true,
              count_mastery: false,
            },
          },
        }),
      )
    }
    await page.setViewportSize({ width: 360, height: 800 })
    await login(page, account)
    await page.getByText('查看任务', { exact: true }).click()
    await expect(page.locator('.assignment-card')).toHaveCount(2)
    await expect(page.locator('.written-answer textarea:visible')).toHaveCount(1)
    const first = page.locator('.assignment-card').filter({ hasText: '第一项：移项练习' })
    const second = page.locator('.assignment-card').filter({ hasText: '第二项：等式练习' })
    if ((await first.locator('.assignment-header').getAttribute('aria-expanded')) !== 'true')
      await first.locator('.assignment-header').click()
    await first.locator('.written-answer textarea').fill('2x=8\nx=4')
    await second.locator('.assignment-header').click()
    await expect(first.locator('.assignment-body')).toBeHidden()
    await expect(second.locator('.assignment-body')).toBeVisible()
    await first.locator('.assignment-header').click()
    await expect(first.locator('.written-answer textarea')).toHaveValue('2x=8\nx=4')
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.screenshot({ path: 'test-results/assignment-simple.png', fullPage: true })
    await button(first, '提交作答').click()
    await expect(first.locator('.assignment-result')).toContainText('等待教师核对')
    await expect(second.locator('.assignment-body')).toBeHidden()
    await expect(page.getByText('待完成 1 项', { exact: true })).toBeVisible()
  })

  test('管理员手机四个分区、学生详情、会话详情和退出可操作且不溢出', async ({ page }) => {
    await login(page, roleAccount('admin'))
    await expect(page.locator('.nav-item')).toHaveCount(4)
    for (const label of ['全局概览', '学生画像', '智能体轨迹', '系统状态']) {
      await page.locator('.nav-item').filter({ hasText: label }).click()
      await expect(page.locator('.nav-item.active')).toContainText(label)
      expect(
        await page.evaluate(
          () =>
            Math.max(document.body.scrollWidth, document.documentElement.scrollWidth) <= innerWidth,
        ),
      ).toBe(true)
    }
    await page.locator('.nav-item').filter({ hasText: '学生画像' }).click()
    await page.locator('.side-list .select-row').first().click()
    await expect(page.locator('.profile')).toBeVisible()
    await page.locator('.nav-item').filter({ hasText: '智能体轨迹' }).click()
    await page.locator('.side-list .select-row').first().click()
    await expect(page.locator('.summary-grid')).toBeVisible()
    expect(
      await page.evaluate(
        () =>
          Math.max(document.body.scrollWidth, document.documentElement.scrollWidth) <= innerWidth,
      ),
    ).toBe(true)
    await button(page, '刷新数据').click()
    await button(page, '退出登录').click()
    await expect(page.getByText('欢迎回来', { exact: true })).toBeVisible()
  })
})

test('注册和修改密码可实际完成，新旧密码状态正确', async ({ page, request }) => {
  const email = `ui-register-${Date.now()}@minddimension.local`
  await page.goto('/#/pages/login/login')
  await page.getByText('注册账号', { exact: true }).click()
  await field(page, '你的名字', '注册验收学生')
  await field(page, '邮箱', email)
  await field(page, '登录密码', 'UiAudit-old-123')
  await page.getByLabel('当前年级', { exact: true }).selectOption('初二')
  await button(page, '创建账号').click()
  await expect(page).toHaveURL(/pages\/index\/index/)
  const oldSession = await data(
    await request.post(API + '/auth/login', { data: { email, password: 'UiAudit-old-123' } }),
  )
  await page.getByRole('button', { name: '我的', exact: true }).click()
  await button(page, '退出登录').click()
  await page.getByText('修改密码', { exact: true }).click()
  await field(page, '账号邮箱', email)
  await field(page, '当前密码', 'UiAudit-old-123')
  await field(page, '新密码', 'UiAudit-new-123')
  await field(page, '确认新密码', 'UiAudit-new-123')
  await button(page, '修改密码').click()
  await expect(page.getByText('欢迎回来', { exact: true })).toBeVisible()
  const old = await request.post(API + '/auth/login', {
    data: { email, password: 'UiAudit-old-123' },
  })
  expect(old.status()).toBe(401)
  expect(
    (
      await request.get(API + '/auth/me', {
        headers: { Authorization: `Bearer ${oldSession.access_token}` },
      })
    ).status(),
  ).toBe(401)
  await login(page, { email, password: 'UiAudit-new-123' })
  await expect(page).toHaveURL(/pages\/index\/index/)
})

test.describe('教师与学生协作', () => {
  test.skip(!roleTests, '显式 QA_ROLE_TESTS=1 启用，所有写入仅用于新建验收班级、题目和学生')
  test.use({
    viewport: { width: 1280, height: 900 },
    screen: { width: 1280, height: 900 },
    isMobile: false,
    hasTouch: false,
  })
  test('创建班级、加入学生、发布题目、布置、作答和教师复核形成闭环', async ({
    page,
    request,
    browser,
  }) => {
    test.setTimeout(120_000)
    const account = await student(request)
    const suffix = Date.now(),
      className = `界面验收班级-${suffix}`,
      questionName = `界面验收题目-${suffix}`,
      assignmentName = `界面验收任务-${suffix}`
    await login(page, roleAccount('teacher'))
    await button(page, '班级与学生').click()
    await page.getByText('新建班级', { exact: true }).click()
    await field(page, '班级名称', className)
    await field(page, '年级', '高一')
    await button(page, '创建').click()
    await page.locator('.teacher-row').filter({ hasText: className }).click()
    await page.getByText('添加学生', { exact: true }).click()
    await field(page, '学生账号邮箱', account.email)
    await button(page, '加入班级').click()
    await expect(page.locator('.teacher-row')).toContainText('界面验收学生')
    await page.locator('.teacher-row').filter({ hasText: '界面验收学生' }).click()
    await page.getByText('查看与调整', { exact: true }).click()
    await expect(page.getByText('暂无学习计划', { exact: true })).toBeVisible()
    await page.goto('/#/pages/teacher/questions')
    await page.getByText('新增题目', { exact: true }).click()
    await field(page, '标题', questionName)
    await field(page, '年级', '高一')
    await field(page, '题干（必填）', '解方程：x+1=3')
    await field(page, '标准答案', 'x=2')
    await field(page, '参考步骤（每行一步）', 'x=3-1\nx=2')
    await page.getByText('允许自动判题', { exact: true }).click()
    await button(page, '发布题目').click()
    await expect(page).toHaveURL(/pages\/teacher\/questions/)
    await expect(page.locator('.teacher-row').filter({ hasText: questionName })).toBeVisible()
    await page.goto('/#/pages/teacher/assignment')
    await field(page, '任务名称', assignmentName)
    await choose(
      page,
      page.locator('.field').filter({ hasText: '选择班级' }).locator('.field-box'),
      className,
    )
    await choose(
      page,
      page.locator('.field').filter({ hasText: '选择题目' }).locator('.field-box'),
      questionName,
    )
    await page.getByText('允许 AI 判题', { exact: true }).click()
    await page.getByText('必须教师批改', { exact: true }).click()
    await button(page, '布置给全班').click()
    await expect(page.locator('.teacher-row').filter({ hasText: assignmentName })).toBeVisible()
    const studentContext = await browser.newContext({
      ignoreHTTPSErrors: process.env.QA_PREVIEW_HTTPS === '1',
      viewport: { width: 390, height: 844 },
      isMobile: true,
      hasTouch: true,
    })
    const studentPage = await studentContext.newPage()
    await login(studentPage, account)
    await studentPage.getByText('查看任务', { exact: true }).click()
    await expect(studentPage.getByText(assignmentName, { exact: true })).toBeVisible()
    await studentPage.locator('.written-answer textarea').fill('x=2')
    await button(studentPage, '提交作答').click()
    await expect(studentPage.getByText('作答已提交，等待教师核对。', { exact: true })).toBeVisible()
    await page.goto('/#/pages/teacher/reviews')
    await page.locator('.teacher-row').filter({ hasText: questionName }).click()
    await page.getByText('确认正确', { exact: true }).click()
    await field(page, '复核理由（必填）', '前端验收：解方程得到x=2，计算正确。')
    await button(page, '确认结论').click()
    await expect(page).toHaveURL(/pages\/teacher\/reviews/)
    await studentPage.reload()
    await expect(
      studentPage.getByText('作答已完成，可查看教师反馈。', { exact: true }),
    ).toBeVisible()
    await page.goto('/#/pages/teacher/audit')
    await expect(page.getByText('人工复核', { exact: true }).first()).toBeVisible()
    await studentContext.close()
  })
})

test.describe('电脑裁剪', () => {
  test.use({
    viewport: { width: 1280, height: 900 },
    screen: { width: 1280, height: 900 },
    isMobile: false,
    hasTouch: false,
  })
  test('四角支持鼠标调整，整图按钮恢复范围', async ({ page, request }) => {
    const account = await student(request)
    await login(page, account)
    const png = await page.evaluate(() => {
      const canvas = document.createElement('canvas')
      canvas.width = 800
      canvas.height = 500
      const ctx = canvas.getContext('2d')!
      ctx.fillStyle = '#fff'
      ctx.fillRect(0, 0, 800, 500)
      ctx.fillStyle = '#202124'
      ctx.font = '32px sans-serif'
      ctx.fillText('Crop UI test: 2x+3=11', 60, 100)
      return canvas.toDataURL('image/png').split(',')[1]
    })
    const ingested = await data(
      await request.post(API + '/questions/ingest', {
        headers: account.headers,
        multipart: {
          file: { name: 'crop-ui.png', mimeType: 'image/png', buffer: Buffer.from(png, 'base64') },
          defer_processing: 'true',
        },
      }),
    )
    await page.goto(`/#/pages/crop/crop?id=${ingested.question_id}`)
    const box = page.locator('.crop-box')
    await expect(box).toBeVisible()
    await expect.poll(async () => (await box.boundingBox())?.width || 0).toBeGreaterThan(100)
    const before = (await box.boundingBox())!,
      handle = (await page.locator('.corner.rb').boundingBox())!
    await page.mouse.move(handle.x + handle.width / 2, handle.y + handle.height / 2)
    await page.mouse.down()
    await page.mouse.move(handle.x + handle.width / 2 - 40, handle.y + handle.height / 2 - 30, {
      steps: 8,
    })
    await page.mouse.up()
    await expect.poll(async () => (await box.boundingBox())!.width).toBeLessThan(before.width - 20)
    await button(page, '选择整张图片').click()
    await expect.poll(async () => (await box.boundingBox())!.width).toBeGreaterThan(before.width)
  })
})

test('学习分类、知识检索与跨页多题组卷保持范围', async ({ page, request }, testInfo) => {
  const account = await student(request)
  for (const params of [
    { grade: '高三' },
    { subject: '数学', grade: '高一' },
    { misconception: '适用条件' },
  ]) {
    const cards = await data(
      await request.get(API + '/knowledge/cards', { headers: account.headers, params }),
    )
    expect(cards.length).toBeGreaterThan(0)
    for (const card of cards) {
      if (params.grade) expect(card.content.grade).toContain(params.grade)
      if (params.subject) expect(card.subject).toBe(params.subject)
      if (params.misconception)
        expect(card.content.common_misconceptions.join(' ')).toContain(params.misconception)
    }
  }
  const first = await manual(request, account, '专项范围甲：2x+3=11')
  const second = await manual(request, account, '专项范围乙：3x+1=13')
  await login(page, account)
  await page.getByRole('button', { name: '学习', exact: true }).click()
  for (const name of ['复习', '练一类题', '考前组卷', '查知识']) {
    await expect(page.getByRole('button', { name, exact: true })).toBeVisible()
  }
  await expect(page.getByRole('button', { name: '复习记录', exact: true })).not.toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('learning-center.png'), fullPage: true })
  await page.getByRole('button', { name: '查知识', exact: true }).focus()
  await page.keyboard.press('Enter')
  await expect(page.locator('.knowledge-result').first()).toBeVisible()
  await page.locator('.knowledge-result').first().click()
  await expect(page.getByText('查看相关错题', { exact: true })).toBeVisible()
  await page.getByText('查看相关错题', { exact: true }).click()
  await expect(page).toHaveURL(/pages\/problem\/list\?subject=/)
  await expect(page.locator('.inline-search input')).not.toHaveValue('')
  expect(await page.locator('.inline-search input').inputValue()).not.toContain('%')
  await page.goto(
    `/#/pages/paper/paper-center?subject=${encodeURIComponent('数学')}&ids=${encodeURIComponent(first.id + ',' + second.id)}`,
  )
  await expect(page.getByText('选择题目（2）', { exact: true })).toBeVisible()
  await expect(page.locator('.candidate.selected')).toHaveCount(2)
  await expect(page.locator('.field-picker').first()).toHaveText('数学')
  // Display fixture only: no AI call or change to persisted learning evidence.
  await page.route('**/questions/' + first.id, async (route) => {
    const response = await route.fetch()
    const payload = await response.json()
    payload.data.analysis = { final_answer: 'x=4', reference_steps: [] }
    await route.fulfill({ response, json: payload })
  })
  await page.goto('/#/pages/detail/detail?id=' + first.id)
  await expect(page.getByText('查看参考答案', { exact: true })).toBeVisible()
  await expect(page.locator('.answer-grid')).not.toContainText('正确答案')
  await page.getByText('查看参考答案', { exact: true }).click()
  await expect(page.locator('.answer-grid')).toContainText('x=4')
  await page.getByText('收起参考答案', { exact: true }).click()
  await expect(page.locator('.answer-grid')).not.toContainText('x=4')
})

test('最终手机布局：窄屏页面、筛选草稿和详情分区保持可用', async ({ page, request }, testInfo) => {
  test.setTimeout(90_000)
  const account = await student(request)
  const question = await manual(
    request,
    account,
    '手机版面核对：在实数范围内解方程2x+3=11，并写出等式两边所做的运算',
  )
  await login(page, account)
  const screens = [
    ['index/index', '从一道做错的题开始'],
    ['learning/learning', '考前组卷'],
    ['problem/list', question.question_text],
    [`detail/detail?id=${question.id}`, '当时的答案'],
    ['analysis/analysis', '还没有学习报告'],
  ]
  for (const width of [360, 390, 430]) {
    await page.setViewportSize({ width, height: 844 })
    for (const [route, label] of screens) {
      await page.goto(`/#/pages/${route}`)
      await expect(page.getByText(label, { exact: true }).first()).toBeVisible()
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
        true,
      )
      if (width === 390)
        await page.screenshot({
          path: testInfo.outputPath(`final-${route.split('/')[0]}.png`),
          fullPage: true,
        })
      if (width === 390) {
        // Browser text-only enlargement, distinct from a native OS font-size test.
        await page.evaluate(() => {
          const sizes = [
            ...document.querySelectorAll<HTMLElement>(
              'uni-text, uni-button, input, textarea, small, b',
            ),
          ]
            .filter((el) => el.getClientRects().length && !el.closest('uni-icons'))
            .map((el) => [el, parseFloat(getComputedStyle(el).fontSize)] as const)
          for (const [el, size] of sizes) {
            el.style.fontSize = `${size * 2}px`
            el.style.lineHeight = '1.5'
          }
        })
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
          true,
        )
        expect(
          await page
            .locator('.primary-btn, .feature-link')
            .evaluateAll((elements) =>
              elements
                .filter((el) => el.getClientRects().length)
                .every((el) => el.scrollHeight <= el.clientHeight + 2),
            ),
        ).toBe(true)
        await page.screenshot({
          path: testInfo.outputPath(`text-200-${route.split('/')[0]}.png`),
          fullPage: true,
        })
      }
    }
  }
  await page.goto('/#/pages/problem/list')
  await page.getByRole('button', { name: '筛选', exact: true }).click()
  await page.getByRole('button', { name: '仅收藏', exact: true }).click()
  await page.getByRole('button', { name: '取消', exact: true }).click()
  await expect(page.locator('.problem-card')).toHaveCount(1)
  await page.locator('.problem-card').click()
  await expect(page.getByRole('button', { name: '针对练习', exact: false })).not.toBeVisible()
  await page.getByRole('button', { name: '学与练', exact: true }).click()
  await expect(page.getByRole('button', { name: '本题知识', exact: false })).toBeVisible()
  await expect(page.getByText('当时的答案', { exact: true })).not.toBeVisible()
  await page.getByRole('button', { name: '题目', exact: true }).click()
  await expect(page.getByText('当时的答案', { exact: true })).toBeVisible()
})

test('本题知识：未分析时不虚构错因，并能进入明确的分析操作', async ({ page, request }) => {
  const account = await student(request)
  const question = await manual(request, account, '解方程：2x+3=11')
  await login(page, account)
  await page.goto(`/#/pages/detail/detail?id=${question.id}`)
  await page.getByRole('button', { name: '学与练', exact: true }).click()
  await page.getByRole('button', { name: '本题知识', exact: false }).click()
  await expect(page.getByText('先核对本题内容', { exact: true })).toBeVisible()
  await expect(page.getByText('先了解本题知识', { exact: true })).toBeVisible()
  await expect(page.getByText('这道题为什么会错', { exact: true })).toHaveCount(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.getByRole('button', { name: '分析这道题', exact: true }).click()
  await expect(page).toHaveURL(/diagnosis\/diagnosis/)
  await expect(button(page, '生成本题解析')).toBeVisible()
})
