import { expect, test } from '@playwright/test'

const API =
  process.env.ZHIWEI_API_URL ||
  `http://127.0.0.1:${process.env.ZHIWEI_BACKEND_PORT || '8000'}/api/v1`
async function data(response: any) {
  expect(response.ok(), `HTTP ${response.status()}`).toBeTruthy()
  const body = await response.json()
  return body.data ?? body
}
async function account(page: any, request: any) {
  const email = `qa-recovery-${Date.now()}-${Math.random().toString(36).slice(2)}@minddimension.local`
  const password = 'RecoveryAudit-123'
  const user = await data(
    await request.post(API + '/auth/register', {
      data: { email, password, name: '恢复验收', grade: '初一' },
    }),
  )
  await page.goto('/#/pages/login/login')
  await page.getByLabel('邮箱', { exact: true }).fill(email)
  await page.getByLabel('密码', { exact: true }).fill(password)
  await page.getByText('登录', { exact: true }).click()
  await expect(page).toHaveURL(/index\/index/)
  return { headers: { Authorization: `Bearer ${user.access_token}` } }
}
function button(scope: any, text: string) {
  return scope.locator('uni-button,button').filter({ hasText: text }).first()
}

test('页面里的旧文件链接失效后，点击打开仍取得新链接且保留编辑内容', async ({ page, request }) => {
  const { headers } = await account(page, request)
  const q = await data(
    await request.post(API + '/questions/manual', {
      headers,
      data: {
        question_text: '恢复验收：解方程2x+3=11',
        subject: '数学',
        grade: '初一',
        student_answer: 'x=7',
      },
    }),
  )
  const paper = await data(
    await request.post(API + '/papers', {
      headers,
      data: { title: '链接恢复验收', question_ids: [q.id] },
    }),
  )
  await data(
    await request.post(API + `/papers/${paper.id}/export`, { headers, data: { kind: 'question' } }),
  )
  let metadataRequests = 0,
    failRenewal = false
  await page.route(`**/papers/${paper.id}`, async (route) => {
    metadataRequests++
    if (failRenewal) return route.fulfill({ status: 503, json: { detail: '文件链接暂时无法更新' } })
    if (metadataRequests > 1) return route.continue()
    const response = await route.fetch(),
      body = await response.json(),
      payload = body.data ?? body
    for (const file of payload.exports) {
      const url = new URL(file.url, API)
      url.searchParams.set('expires', '1')
      file.url = url.pathname + url.search
      expect((await request.get(new URL(file.url, API).href)).status()).toBe(403)
    }
    await route.fulfill({ response, json: body })
  })
  await page.goto('/#/pages/paper/paper-center')
  await page.locator('.list-card').filter({ hasText: '链接恢复验收' }).click()
  await page.locator('.editor-title input').fill('尚未保存的新标题')
  const opened = page.context().waitForEvent('response', {
    predicate: (r) => new URL(r.url()).pathname.startsWith('/reports/'),
  })
  await page.locator('.download-row').filter({ hasText: '题目 PDF' }).click()
  expect((await opened).status()).toBe(200)
  expect(metadataRequests).toBeGreaterThan(1)
  await expect(page.locator('.editor-title input')).toHaveValue('尚未保存的新标题')
  for (const popup of page.context().pages()) if (popup !== page) await popup.close()
  failRenewal = true
  await page.locator('.download-row').filter({ hasText: '题目 PDF' }).click()
  await expect(page.getByText('文件链接暂时无法更新', { exact: true })).toBeVisible()
  await expect.poll(() => page.context().pages().length).toBe(1)
  await expect(page.locator('.editor-title input')).toHaveValue('尚未保存的新标题')
  failRenewal = false
  const retried = page.context().waitForEvent('response', {
    predicate: (r) => new URL(r.url()).pathname.startsWith('/reports/'),
  })
  await page.locator('.download-row').filter({ hasText: '题目 PDF' }).click()
  expect((await retried).status()).toBe(200)
  for (const popup of page.context().pages()) if (popup !== page) await popup.close()
})

test('求助取消、发送失败、作答失败与回退失败都保留当前输入并可重试', async ({ page, request }) => {
  await account(page, request)
  // Public task fixtures isolate browser recovery from model availability.
  const session: any = {
    id: 'qa-recovery-session',
    stage: 'near_transfer',
    status: 'active',
    knowledge_title: '等式的性质',
    turns: [],
    activity: {
      id: 'near-recovery',
      type: 'variant',
      question: '解方程3x+4=19',
      input_mode: 'calculation',
      attempt: 1,
      max_attempts: 2,
    },
  }
  await page.route('**/tutor/sessions/qa-recovery-session', (route) =>
    route.fulfill({ json: { data: session } }),
  )
  let failHelp = true,
    helpRequests = 0,
    answerRequests = 0,
    rewindRequests = 0
  await page.route('**/tutor/sessions/qa-recovery-session/turns', async (route) => {
    helpRequests++
    if (failHelp) return route.fulfill({ status: 503, json: { detail: '求助暂时不可用' } })
    session.turns = [
      { id: 'q', role: 'user', content: route.request().postDataJSON().message },
      { id: 'a', role: 'assistant', content: '两边同时减去4，等式关系保持不变。' },
    ]
    await route.fulfill({ json: { data: {} } })
  })
  await page.route('**/tutor/sessions/qa-recovery-session/activity/answer', (route) => {
    answerRequests++
    return route.fulfill({ status: 503, json: { detail: '判定暂时不可用' } })
  })
  await page.route('**/tutor/sessions/qa-recovery-session/rewind', (route) => {
    rewindRequests++
    return route.fulfill({ status: 503, json: { detail: '回退暂时不可用' } })
  })
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.goto('/#/pages/tutor/tutor?id=qa-recovery-session')
  await page.locator('.answer-area textarea').nth(0).fill('x=5')
  await page.locator('.answer-area textarea').nth(1).fill('3x=15，再两边除以3')
  await button(page, '问小智老师').click()
  await page.locator('.helper-bar input').fill('为什么两边要同时减4？')
  await button(page, '取消').click()
  expect(helpRequests).toBe(0)
  await button(page, '问小智老师').click()
  await expect(page.locator('.helper-bar input')).toHaveValue('为什么两边要同时减4？')
  await button(page, '发送').click()
  await expect(button(page, '发送')).not.toHaveAttribute('disabled', 'true')
  await expect(page.locator('.helper-bar input')).toHaveValue('为什么两边要同时减4？')
  failHelp = false
  await button(page, '发送').click()
  await expect(page.locator('.history-list')).toContainText('两边同时减去4')
  await expect(page.locator('.answer-area textarea').nth(0)).toHaveValue('x=5')
  await expect(page.locator('.answer-area textarea').nth(1)).toHaveValue('3x=15，再两边除以3')
  await button(page, '提交答案').click()
  await expect(button(page, '提交答案')).not.toHaveAttribute('disabled', 'true')
  await expect(page.locator('.answer-area textarea').nth(0)).toHaveValue('x=5')
  await button(page, '返回上一步').click()
  await expect(page.locator('.rewind-button')).not.toHaveAttribute('disabled', 'true')
  await expect(page.locator('.answer-area textarea').nth(0)).toHaveValue('x=5')
  expect(helpRequests).toBe(2)
  expect(answerRequests).toBe(1)
  expect(rewindRequests).toBe(1)
  expect(errors).toEqual([])
})

test('归档取消的识别任务立即停止等待，裁剪和核对页均可返回错题本', async ({ page, request }) => {
  await account(page, request)
  const svg =
    'data:image/svg+xml,' +
    encodeURIComponent(
      '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="500"><rect width="800" height="500" fill="white"/><text x="50" y="100" font-size="40">2x+3=11</text></svg>',
    )
  const question = {
    id: 'qa-cancelled-question',
    status: 'processing',
    question_text: '解方程2x+3=11',
    assets: [{ kind: 'original', url: svg }],
  }
  await page.route('**/questions/qa-cancelled-question', (route) =>
    route.fulfill({ json: { data: question } }),
  )
  let cropRequests = 0,
    polls = 0
  await page.route('**/questions/qa-cancelled-question/crop', (route) => {
    cropRequests++
    return route.fulfill({ json: { data: { job_id: 'qa-cancelled-job' } } })
  })
  await page.route('**/jobs/qa-cancelled-job', (route) => {
    polls++
    return route.fulfill({
      json: { data: { status: 'cancelled', error: '题目已归档，识别任务已取消' } },
    })
  })
  await page.goto('/#/pages/crop/crop?id=qa-cancelled-question')
  await button(page, '开始识别').click()
  await expect(page.getByText('题目已归档，识别任务已取消', { exact: true })).toBeVisible()
  await button(page, '返回错题本').click()
  await expect(page).toHaveURL(/problem\/list/)
  await page.goto('/#/pages/ocr/ocr?id=qa-cancelled-question&job=qa-cancelled-job')
  await expect(page.getByText('题目已归档，识别任务已取消', { exact: true })).toBeVisible()
  await button(page, '返回错题本').click()
  await expect(page).toHaveURL(/problem\/list/)
  expect(cropRequests).toBe(1)
  expect(polls).toBe(2)
})

test('裁剪提交后刷新继续原任务，断网恢复不重新创建识别', async ({ page, request }) => {
  await account(page, request)
  const svg =
    'data:image/svg+xml,' +
    encodeURIComponent(
      '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="500"><rect width="800" height="500" fill="white"/><text x="50" y="100" font-size="40">3x+4=19</text></svg>',
    )
  let submitted = false,
    complete = false,
    failPoll = false,
    crops = 0,
    polls = 0
  const job = () => ({
    id: 'qa-resume-job',
    kind: 'crop',
    status: complete ? 'completed' : 'running',
    progress: 55,
  })
  await page.route('**/questions/qa-resume-question', (route) =>
    route.fulfill({
      json: {
        data: {
          id: 'qa-resume-question',
          status: complete ? 'needs_confirmation' : submitted ? 'processing' : 'awaiting_crop',
          question_text: complete ? '解方程3x+4=19' : '',
          student_answer: '',
          subject: '数学',
          grade: '初一',
          assets: [
            { kind: 'original', url: svg },
            ...(submitted ? [{ kind: 'crop', url: svg, bbox: [0, 0, 1, 1] }] : []),
          ],
          processing_job: submitted && !complete ? job() : null,
          crop_box: submitted ? [0, 0, 1, 1] : null,
          student_steps: [],
          teacher_marks: [],
        },
      },
    }),
  )
  await page.route('**/questions/qa-resume-question/crop', (route) => {
    crops++
    submitted = true
    return route.fulfill({ json: { data: { job_id: 'qa-resume-job' } } })
  })
  await page.route('**/jobs/qa-resume-job', (route) => {
    polls++
    return failPoll
      ? route.fulfill({ status: 503, json: { detail: '连接暂时中断' } })
      : route.fulfill({ json: { data: job() } })
  })
  await page.goto('/#/pages/crop/crop?id=qa-resume-question')
  await button(page, '选择整张图片').click()
  await button(page, '开始识别').click()
  await expect.poll(() => polls).toBeGreaterThan(0)
  await page.reload()
  await expect(page.locator('.crop-panel .primary-btn')).toHaveAttribute('disabled', 'true')
  expect(crops).toBe(1)
  failPoll = true
  await expect(page.getByText('连接暂时中断', { exact: true }).first()).toBeVisible()
  await expect(button(page, '查看识别结果')).not.toHaveAttribute('disabled', 'true')
  failPoll = false
  complete = true
  await button(page, '查看识别结果').click()
  await expect(page).toHaveURL(/ocr\/ocr/)
  await expect(page.locator('.question-section')).toContainText('3x')
  expect(crops).toBe(1)
})
