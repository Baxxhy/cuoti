// Original new-user acceptance; only browser storage/control adapters changed.
import { expect, test, type Page } from '@playwright/test'

async function registerAndLogin(page: Page) {
  const email = `e2e-new-${Date.now()}@minddimension.local`
  const password = '123456'
  const apiURL =
    process.env.SCZX_API_URL ||
    `http://127.0.0.1:${process.env.SCZX_BACKEND_PORT || '8000'}/api/v1`
  const registration = await page.request.post(`${apiURL}/auth/register`, {
    data: { email, password, name: '新学生', grade: '高一' },
  })
  expect(registration.ok()).toBeTruthy()

  await page.goto('/#/pages/login/login')
  await page.getByLabel('邮箱', { exact: true }).fill(email)
  await page.getByLabel('密码', { exact: true }).fill(password)
  await page.getByText('登录', { exact: true }).click()

  await expect(page).toHaveURL(/#\/pages\/index\/index/)
}

test('真实新学生登录后有明确学习起点，且不伪造个人学习记录', async ({ page }, testInfo) => {
  await registerAndLogin(page)
  const brand = page.getByRole('heading', { name: '错题帮', exact: true })
  await expect(brand).toBeVisible()
  await expect(page.locator('.home-grade')).toHaveText('高一')
  await expect(page.getByRole('heading', { name: '今日', exact: true })).toHaveCount(0)
  const brandBox = await brand.boundingBox()
  const cardBox = await page.locator('.focus-card').boundingBox()
  expect(Math.abs(brandBox!.x - cardBox!.x)).toBeLessThan(2)
  await expect(page.locator('.focus-title')).toHaveText('录入错题')
  await expect(page.locator('.home-starter')).toContainText('知识卡片')
  await expect(page.getByRole('button', { name: '学习设置', exact: true })).toHaveCount(0)
  await expect(page.locator('.focus-card .primary-btn')).toHaveCount(1)
  await expect(page.locator('.focus-card .primary-btn')).toHaveText('拍照或选择图片')
  await expect(page.getByRole('button', { name: '题库练习', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '模拟考试', exact: true })).toBeVisible()
  await expect(page.getByRole('navigation').getByRole('button', { name: '录入错题' })).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('today-current.png'), fullPage: true })
})

test('题库默认按学生学段和学科打开，明确选择后可以切换', async ({ page }) => {
  await registerAndLogin(page)
  const loaded = page.waitForResponse((r) => r.url().includes('/api/v1/study-bank?'))
  await page.getByRole('button', { name: '题库练习', exact: true }).click()
  const response = await loaded
  expect(response.ok()).toBe(true)
  const url = new URL(response.url())
  expect(url.searchParams.get('subject')).toBe('数学')
  expect(url.searchParams.get('grade_band')).toBe('高中')
  const bank = (await response.json()).data
  expect(bank.questions.length).toBeGreaterThan(0)
  expect(bank.questions.every((q) => q.subject === '数学' && q.grade_band === '高中')).toBe(true)
  await expect(page.locator('.bank-picker')).toHaveCount(0)
  await expect(page.getByRole('button', { name: '练 5 题', exact: true })).toBeVisible()
  const switched = page.waitForResponse(
    (r) =>
      r.url().includes('/api/v1/study-bank?') &&
      new URL(r.url()).searchParams.get('subject') === '',
  )
  await page.getByRole('button', { name: '全部', exact: true }).click()
  const allSubjects = await switched
  expect(new URL(allSubjects.url()).searchParams.get('grade_band')).toBe('高中')
  const mixed = (await allSubjects.json()).data
  expect(mixed.questions.every((q) => q.grade_band === '高中')).toBe(true)
  expect(new Set(mixed.questions.map((q) => q.subject)).size).toBeGreaterThan(1)
  const reshuffled = page.waitForResponse(
    (r) =>
      r.url().includes('/api/v1/study-bank?') &&
      new URL(r.url()).searchParams.get('subject') === '',
  )
  await page.getByRole('button', { name: '全部', exact: true }).click()
  const refreshed = (await (await reshuffled).json()).data
  expect(refreshed.shuffle_seed).not.toBe(mixed.shuffle_seed)
  expect(refreshed.questions.map((q) => q.id)).not.toEqual(mixed.questions.map((q) => q.id))
  const englishLoaded = page.waitForResponse(
    (r) =>
      r.url().includes('/api/v1/study-bank?') &&
      new URL(r.url()).searchParams.get('subject') === '英语',
  )
  await page.getByRole('button', { name: '英语', exact: true }).click()
  const english = (await (await englishLoaded).json()).data
  expect(english.questions.length).toBeGreaterThan(0)
  expect(english.questions.every((q) => q.subject === '英语' && q.grade_band === '高中')).toBe(true)
})

test('全部功能页：新学生核心入口显示真实空状态且没有运行异常', async ({ page }, testInfo) => {
  const pageErrors: string[] = []
  page.on('pageerror', (error) => pageErrors.push(error.message))
  await registerAndLogin(page)
  const pages = [
    ['problem/list', '还没有错题'],
    ['review/review', '今天没有待复习题目'],
    ['analysis/analysis', '还没有学习报告'],
    ['paper/paper-center', '当前筛选条件下没有可用错题'],
    ['profile/profile', '使用与帮助'],
    ['learning/learning', '错题组卷'],
    ['library/library', '知识卡片'],
    ['help/help', '使用指南'],
  ]
  for (const [path, expectedText] of pages) {
    await page.goto(`/#/pages/${path}`)
    await expect(page.getByText(expectedText, { exact: true }).first()).toBeVisible()
    await expect(page.locator('body')).not.toContainText('[object Object]')
    expect(await page.evaluate(() => document.body.scrollWidth <= innerWidth)).toBe(true)
    if (['learning/learning', 'library/library'].includes(path)) {
      await page.screenshot({
        path: testInfo.outputPath(path.replace('/', '-') + '.png'),
        fullPage: true,
      })
    }
  }
  expect(pageErrors).toEqual([])
})

test('刷新保留登录，失效凭据跳转回登录页', async ({ page }) => {
  await registerAndLogin(page)
  await page.reload()
  await expect(page.locator('.focus-title')).toHaveText('录入错题')
  await page.evaluate(() => {
    localStorage.setItem('minddimension_access_token', JSON.stringify('invalid-session-for-e2e'))
  })
  await page.goto('/#/pages/profile/profile')
  // UniApp 把 pages.json 的首个登录页规范化为 /#/。
  await expect(page).toHaveURL(/#\/(?:pages\/login\/login)?$/)
  await expect(page.getByRole('form', { name: '登录账号', exact: true })).toBeVisible()
  await expect(page.getByLabel('邮箱', { exact: true })).toBeVisible()
  await expect(page.getByLabel('密码', { exact: true })).toBeVisible()
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem('minddimension_access_token') || 'null'))).toBeNull()
})

test('手动录题保存到错题本，学习档案只显示已完成的阶段', async ({ page }, testInfo) => {
  await registerAndLogin(page)
  await page.getByRole('navigation').getByRole('button', { name: '录入错题' }).click()
  await expect(page).toHaveURL(/#\/pages\/capture\/capture/)
  await expect(page.getByText('拍照或选择图片', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '手动录入错题', exact: true }).click()
  await expect(page).toHaveURL(/#\/pages\/manual\/manual/)
  const save = page.getByText('保存并查看错题', { exact: true })
  // Native disabled buttons cannot be clicked by a user.
  await expect(save).toBeDisabled()
  await save.evaluate((button: HTMLButtonElement) => button.click())
  await expect(page).toHaveURL(/#\/pages\/manual\/manual/)
  await page
    .locator('.field')
    .filter({ hasText: '完整题目' })
    .locator('textarea')
    .fill('解方程：2x+3=11')
  await page.locator('.field').filter({ hasText: '我当时的答案' }).locator('textarea').fill('x=7')
  await page
    .locator('.field')
    .filter({ hasText: '我的解题步骤' })
    .locator('textarea')
    .fill('2x=11+3\nx=7')
  await save.click()
  await expect(page).toHaveURL(/#\/pages\/detail\/detail\?id=/)
  await expect(page.getByText('解方程：2x+3=11', { exact: true }).first()).toBeVisible()
  const questionId = new URLSearchParams(page.url().split('?')[1]).get('id')
  expect(questionId).toBeTruthy()
  await page.getByText('收藏题目', { exact: true }).click()
  await expect(page.getByText('取消收藏', { exact: true })).toBeVisible()
  await page.reload()
  await expect(page.getByText('取消收藏', { exact: true })).toBeVisible()
  await page.goto('/#/pages/problem/list?favorite=1')
  await expect(page.getByText('解方程：2x+3=11', { exact: true })).toBeVisible()
  await page.getByText('按当前条件组卷', { exact: true }).click()
  await expect(page.getByText('选择题目（1）', { exact: true })).toBeVisible()
  await expect(page.locator('.candidate.selected')).toHaveCount(1)
  await page.screenshot({ path: testInfo.outputPath('filtered-paper.png'), fullPage: true })
  await page.goto(`/#/pages/journey/journey?id=${questionId}`)
  await expect(page.getByText('开始错因诊断', { exact: true })).toBeVisible()
  await expect(page.getByText('参考答案待核对', { exact: true })).toBeVisible()
  await expect(page.locator('.stage-row').filter({ hasText: '类似题检验' })).toContainText('待完成')
  await page.screenshot({ path: testInfo.outputPath('learning-journey.png'), fullPage: true })
  await page.goto('/#/pages/problem/list')
  await expect(page.getByText('解方程：2x+3=11', { exact: true })).toBeVisible()
})

test('图片录入保留上传原件，签名下载与原始PNG逐字节一致', async ({ page }) => {
  await registerAndLogin(page)
  const token = await page.evaluate(() => JSON.parse(localStorage.getItem('minddimension_access_token') || 'null'))
  const apiURL =
    process.env.SCZX_API_URL ||
    `http://127.0.0.1:${process.env.SCZX_BACKEND_PORT || '8000'}/api/v1`
  const png = Buffer.from(
    await page.evaluate(() => {
      const canvas = document.createElement('canvas')
      canvas.width = 320
      canvas.height = 200
      const ctx = canvas.getContext('2d')!
      ctx.fillStyle = '#fff'
      ctx.fillRect(0, 0, 320, 200)
      ctx.fillStyle = '#002fa7'
      ctx.font = '24px sans-serif'
      ctx.fillText('2x + 3 = 11', 20, 70)
      return canvas.toDataURL('image/png').split(',')[1]
    }),
    'base64',
  )
  const headers = { Authorization: `Bearer ${token}` }
  const response = await page.request.post(apiURL + '/questions/ingest', {
    headers,
    multipart: {
      file: { name: 'misleading.jpg', mimeType: 'image/jpeg', buffer: png },
      defer_processing: 'true',
    },
  })
  expect(response.ok()).toBeTruthy()
  const created = (await response.json()).data
  expect(created.job_id).toBeNull()
  const detail = await page.request.get(apiURL + '/questions/' + created.question_id, { headers })
  const question = (await detail.json()).data
  const uploaded = question.assets.find((asset: any) => asset.kind === 'uploaded_original')
  expect(uploaded.path).toMatch(/uploaded\.png$/)
  const file = await page.request.get(new URL(uploaded.url, apiURL).href)
  expect(file.ok()).toBeTruthy()
  expect(file.headers()['content-type']).toContain('image/png')
  expect(await file.body()).toEqual(png)
  await page.goto('/#/pages/detail/detail?id=' + created.question_id)
  await expect(page.getByText('查看原图', { exact: true })).toBeVisible()
  await page.getByText('查看原图', { exact: true }).click()
  await expect(page.locator('body')).not.toContainText('[object Object]')
})

test('手动多选题保留结构化选项，无图片题也可以打开修改', async ({ page }, testInfo) => {
  await registerAndLogin(page)
  await page.goto('/#/pages/manual/manual')
  const questionType = page.locator('.field').filter({ hasText: '题型' }).locator('.picker-value')
  await questionType.click()
  await page.locator('.web-selector-content .web-selector-item').filter({hasText:'多选题'}).click()
  await page.locator('.web-selector-action.confirm').click()
  await expect(questionType).toContainText('多选题')
  await page
    .locator('.field')
    .filter({ hasText: '完整题目' })
    .locator('textarea')
    .fill('下列哪些数是偶数？')
  await page.locator('.option-editor textarea').nth(0).fill('2')
  await page.locator('.option-editor textarea').nth(1).fill('4')
  await page.getByText('添加选项', { exact: true }).click()
  await page.locator('.option-editor textarea').nth(2).fill('5')
  await page.locator('.field').filter({ hasText: '我当时的答案' }).locator('textarea').fill('A,C')
  await page.getByText('保存并查看错题', { exact: true }).click()
  await expect(page).toHaveURL(/#\/pages\/detail\/detail\?id=/)
  await expect(page.getByText('下列哪些数是偶数？', { exact: true })).toBeVisible()
  await expect(page.locator('.question-options > *')).toHaveCount(3)
  await expect(page.locator('.question-options')).toContainText('A. 2')
  await expect(page.locator('.question-options')).toContainText('B. 4')
  await expect(page.locator('.question-options')).toContainText('C. 5')
  await page.screenshot({ path: testInfo.outputPath('manual-multiple-choice.png'), fullPage: true })
  await page.getByText('修改录入内容', { exact: true }).click()
  await expect(page).toHaveURL(/#\/pages\/ocr\/ocr\?id=.*edit=1/)
  await expect(page.locator('.question-editor textarea')).toHaveValue('下列哪些数是偶数？')
  await expect(page.locator('.option-edit input')).toHaveCount(3)
  await expect(page.locator('.option-edit input').nth(2)).toHaveValue('5')
  await expect(page.getByText('题目图片暂时无法显示', { exact: true })).toHaveCount(0)
  await page.screenshot({
    path: testInfo.outputPath('manual-edit-without-image.png'),
    fullPage: true,
  })
})

test('练习题源类型：单选互斥、多选按题目顺序提交，短公式留在句内', async ({ page }) => {
  await registerAndLogin(page)
  let type = 'multiple-choice'
  let submitted = ''
  // Only this UI contract uses controlled responses; native grading is covered separately.
  await page.route('**/api/v1/practice/recommend', (route) =>
    route.fulfill({
      json: {
        data: {
          question_id: 'choice-ui-fixture',
          subject: '数学',
          grade: '初中',
          question_type: type,
          stem: '若 $$x=2$$，请选择符合条件的选项。',
          images: [],
          options: [
            { key: 'A', text: '$$2$$' },
            { key: 'B', text: '$$3$$' },
            { key: 'C', text: '$$4$$' },
          ],
        },
      },
    }),
  )
  await page.route('**/api/v1/practice/attempt', (route) => {
    submitted = route.request().postDataJSON().student_answer
    return route.fulfill({
      json: { data: { correct: true, can_update_learning: false, feedback: '测试作答已接收' } },
    })
  })
  await page.goto('/#/pages/practice/practice?id=choice-ui-fixture')
  await expect(page.locator('.question-card .source').first()).toContainText('单选题')
  await expect(page.locator('input[type=radio]')).toHaveCount(3)
  await expect(page.locator('.question-stem .katex-display')).toHaveCount(0)
  await page.locator('.option').nth(0).click()
  await page.locator('.option').nth(2).click()
  await page.getByRole('button', { name: '提交答案', exact: true }).click()
  await expect(page.getByText('测试作答已接收', { exact: true })).toBeVisible()
  expect(submitted).toBe('C')

  type = 'multiple-response'
  await page.getByRole('button', { name: '再练一道', exact: true }).click()
  await expect(page.locator('.question-card .source').first()).toContainText('多选题')
  await expect(page.locator('input[type=checkbox]')).toHaveCount(3)
  await page.locator('.option').nth(2).click()
  await page.locator('.option').nth(0).click()
  await page.getByRole('button', { name: '提交答案', exact: true }).click()
  await expect(page.getByText('测试作答已接收', { exact: true })).toBeVisible()
  expect(submitted).toBe('A、C')
})

test.describe('桌面布局', () => {
  test.use({
    viewport: { width: 1280, height: 900 },
    screen: { width: 1280, height: 900 },
    isMobile: false,
    hasTouch: false,
  })
  test('登录表单与学习内容保持可读宽度，桌面侧栏可操作', async ({ page }) => {
    await page.goto('/#/pages/login/login')
    await expect(page.getByRole('form', { name: '登录账号', exact: true })).toBeVisible()
    const form = await page.getByRole('form', { name: '登录账号', exact: true }).boundingBox()
    expect(form?.width).toBeLessThanOrEqual(480)
    expect(form?.x).toBeGreaterThan(300)
    await registerAndLogin(page)
    await expect(page.locator('.focus-card .primary-btn')).toBeVisible()
    const main = await page.locator('.home-page').boundingBox()
    expect(main?.width).toBeLessThanOrEqual(1180)
    const button = await page.locator('.focus-card .primary-btn').boundingBox()
    expect(button?.height).toBeGreaterThanOrEqual(44)
    expect(button?.height).toBeLessThanOrEqual(52)
    await page.getByRole('button', { name: '错题', exact: true }).click()
    await expect(page).toHaveURL(/#\/pages\/problem\/list/)
    await expect(page.getByText('还没有错题', { exact: true })).toBeVisible()
    expect(await page.evaluate(() => document.body.scrollWidth <= innerWidth)).toBe(true)
  })
})

test('知识卡片默认个人年级，个人中心入口可用键盘打开', async ({ page }) => {
  await registerAndLogin(page)
  const cards = page.waitForResponse((response) =>
    response.url().includes('/api/v1/knowledge/cards?'),
  )
  await page.getByRole('button', { name: '知识卡片', exact: true }).click()
  const response = await cards
  expect(response.ok()).toBe(true)
  expect(new URL(response.url()).searchParams.get('grade')).toBe('高一')
  await expect(page.locator('.filter-button').last()).toContainText('高一')
  await page.goto('/#/pages/profile/profile')
  const entry = page.getByRole('button', { name: '编辑个人资料', exact: true })
  await entry.focus()
  await expect(entry).toBeFocused()
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(/pages\/profile\/edit/)
  await page.getByRole('button', { name: '返回', exact: true }).click()
  const help = page.getByRole('button', { name: '使用指南', exact: true })
  await help.focus()
  await page.keyboard.press('Space')
  await expect(page).toHaveURL(/pages\/help\/help/)
})
