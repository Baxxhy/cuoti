// Original functional audit; native controls adapted; desktop crop is extended in crop.spec.ts.
import { expect, test, type Page, type APIRequestContext } from '@playwright/test'

const API =
  process.env.SCZX_API_URL ||
  `http://127.0.0.1:${process.env.SCZX_BACKEND_PORT || '8000'}/api/v1`
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
  await expect(page).toHaveURL(/#\/pages\/(?:index\/index|admin\/workbench)(?:[?]|$)/)
  await expect(page.getByRole('form', { name: '登录账号', exact: true })).toHaveCount(0)
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
  // Database flows are checked separately; no live model is called by this fixture.
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
  const track = page.locator('input[type=range]')
  const trackBox=await track.boundingBox()
  await track.tap({ position: { x: 5, y: trackBox!.height/2 } })
  await expect(page.locator('.control b')).not.toHaveText('3')
  await page.locator('.field-textarea textarea').fill('两边同时减去3仍相等。')
  await button(page, '保存观察并返回').click()
  await expect(page).toHaveURL(/tutor\/tutor/)
  await expect(page.locator('.answer-area textarea').first()).toBeVisible()
  await expect(button(page, '讲完了')).toBeDisabled()
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
  await button(page, '提交作答').click()
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
  await page.getByRole('button', { name: '学习记录', exact: true }).click()
  await page.getByText('我的完整步骤', { exact: true }).click()
  await expect(page.locator('.fold-body')).toContainText('2x=11+3')
  await page.getByText('我的完整步骤', { exact: true }).click()
  await expect(page.locator('.fold-body')).toHaveCount(0)
  await page.getByRole('button', { name: '题目与错因', exact: true }).click()
  await expect(page.getByText('参考步骤', { exact: true })).not.toBeVisible()
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

test('组卷高级筛选、保存、排序与导出真实生效，缺解析的答案卷被阻止', async ({ page, request }) => {
  const account = await student(request)
  await manual(request, account, '组卷验收题一：2x+3=11')
  await manual(request, account, '组卷验收题二：x+5=9')
  await login(page, account)
  await page.getByRole('button', { name: '学习', exact: true }).click()
  await page.getByRole('button', { name: '错题组卷', exact: true }).click()
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
  await expect(button(page, '保存名称、排序与分值')).toBeEnabled()
  await expect(page.locator('.total-score')).toContainText('25')
  for (const label of ['题目 PDF', '学习表格']) {
    await expect(button(page, label)).toBeEnabled()
    const exported = page.waitForResponse(
      (response) => response.url().endsWith('/export') && response.request().method() === 'POST',
    )
    await button(page, label).click()
    expect((await exported).ok()).toBe(true)
    await expect(page.locator('.download-row')).toHaveCount(
      ['题目 PDF', '学习表格'].indexOf(label) + 1,
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
  await expect(button(page, '补齐解析并导出答案')).toBeVisible()
  const incompleteAnswer = await request.post(API + '/papers/' + paper.id + '/export', {
    headers: account.headers,
    data: { kind: 'answer' },
  })
  expect(incompleteAnswer.status()).toBe(409)
  expect(paper.exports.every((file: any) => file.kind !== 'answer')).toBeTruthy()
  expect(paper.items.reduce((sum: number, item: any) => sum + item.score, 0)).toBe(25)
  expect(paper.exports).toHaveLength(2)
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
  test.beforeAll(()=>expect(roleTests, '需要隔离管理员样本').toBe(true))
  test.use({
    viewport: { width: 390, height: 844 },
    screen: { width: 390, height: 844 },
    isMobile: true,
    hasTouch: true,
  })

  test('管理员手机四个分区、学生详情、会话详情和退出可操作且不溢出', async ({ page }) => {
    const workbench = page.waitForResponse(
      (response) => new URL(response.url()).pathname === '/api/v1/admin/workbench',
    )
    await login(page, roleAccount('admin'))
    expect((await workbench).ok()).toBe(true)
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
    await expect(page.getByRole('form', { name: '登录账号', exact: true })).toBeVisible()
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
  await expect(page.getByRole('form', { name: '登录账号', exact: true })).toBeVisible()
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
  for (const name of ['到期复习', '类似题练习', '错题组卷', '知识框架']) {
    await expect(page.getByRole('button', { name, exact: true })).toBeVisible()
  }
  await expect(page.getByRole('button', { name: '复习记录', exact: true })).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('learning-center.png'), fullPage: true })
  await page.getByRole('button', { name: '知识框架', exact: true }).focus()
  await page.keyboard.press('Enter')
  await expect(page.locator('.knowledge-node, .direct-knowledge').first()).toBeVisible()
  await page.locator('.knowledge-node, .direct-knowledge').first().click()
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
    ['index/index', '录入错题'],
    ['learning/learning', '错题组卷'],
    ['problem/list', question.question_text],
    [`detail/detail?id=${question.id}`, '我当时的答案'],
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
              'span, button, input, textarea, small, b',
            ),
          ]
            .filter((el) => el.getClientRects().length && !el.closest('.web-icon'))
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
  await expect(page.getByRole('button', { name: '类似题练习', exact: false })).not.toBeVisible()
  await page.getByRole('button', { name: '解析与练习', exact: true }).click()
  await expect(page.getByRole('button', { name: '相关知识', exact: false })).toBeVisible()
  await expect(page.getByText('我当时的答案', { exact: true })).not.toBeVisible()
  await page.getByRole('button', { name: '题目与错因', exact: true }).click()
  await expect(page.getByText('我当时的答案', { exact: true })).toBeVisible()
})

test('本题知识：点击分析后自动启动，进度、失败重试和结果保持一致', async ({ page, request }) => {
  const account = await student(request)
  const question = await manual(request, account, '解方程：2x+3=11')
  let calls = 0
  let finished = false
  let release: () => void = () => {}
  const pending = new Promise<void>((resolve) => {
    release = resolve
  })
  await page.route(`**/api/v1/questions/${question.id}/diagnose`, async (route) => {
    calls++
    if (calls === 1) {
      await pending
      await route.fulfill({ status: 503, json: { detail: '学习服务暂时繁忙，请重试。' } })
    } else {
      finished = true
      await route.fulfill({ json: { data: {} } })
    }
  })
  await page.route(`**/api/v1/questions/${question.id}`, async (route) => {
    const response = await route.fetch()
    const body = await response.json()
    if (finished)
      body.data = {
        ...body.data,
        analysis: { final_answer: 'x=4' },
        reference_steps: [{ id: 'ref', text: '2x=8，x=4' }],
        diagnosis: {
          first_error_step: 0,
          error_type: 'sign_error',
          root_misconception: '移项时要改变符号。',
          counterfactual: {},
        },
      }
    await route.fulfill({ response, json: body })
  })
  await login(page, account)
  await page.goto(`/#/pages/detail/detail?id=${question.id}`)
  await page.getByRole('button', { name: '解析与练习', exact: true }).click()
  await page.getByRole('button', { name: '相关知识', exact: false }).click()
  await expect(page.getByText('先核对本题内容', { exact: true })).toBeVisible()
  await expect(page.getByText('先了解本题知识', { exact: true })).toBeVisible()
  await expect(page.getByText('这道题为什么会错', { exact: true })).toHaveCount(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.getByRole('button', { name: '分析这道题', exact: true }).click()
  await expect(page).toHaveURL(/diagnosis\/diagnosis/)
  await expect(page.getByText('正在分析错因', { exact: true })).toBeVisible()
  await expect(button(page, '生成本题解析')).toHaveCount(0)
  expect(calls).toBe(1)
  release()
  await expect(page.getByText('分析未完成', { exact: true })).toBeVisible()
  await expect(page.getByText('正在分析错因', { exact: true })).toHaveCount(0)
  await page.getByRole('button', { name: '重新分析', exact: true }).click()
  await expect(page.getByText('移项时要改变符号。', { exact: true }).first()).toBeVisible()
  expect(calls).toBe(2)
})
