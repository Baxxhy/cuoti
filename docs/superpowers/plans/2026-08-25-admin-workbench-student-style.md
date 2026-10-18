# 管理员工作台学生端同源改版实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 将管理员只读工作台改成与学生端一致的蓝白大字号界面，并用真实数据增加学习闭环、会话分布和认知变化图形。

**架构：** 保持现有三个管理员 GET 接口不变。新增一个纯前端视图模型模块，将接口响应转换成概览指标、学习闭环节点和会话占比；工作台 Vue 页面只负责查询、选择和渲染。图形使用 CSS 与 `uni-icons`，不引入图表依赖。

**技术栈：** Vue 3、UniApp、JavaScript、SCSS、Vitest、Uni UI icons

---

## 文件职责

- 创建 `frontend/src/pages/admin/workbench-data.js`：把管理员接口响应转换为可测试的图表和指标数据。
- 修改 `frontend/src/pages/admin/workbench.vue`：重写页面结构、交互和学生端同源样式。
- 修改 `frontend/tests/admin-workbench.test.ts`：验证真实数据转换、只读请求边界和页面构建契约。

### 任务 1：建立真实数据视图模型

**文件：**
- 创建：`frontend/src/pages/admin/workbench-data.js`
- 修改：`frontend/tests/admin-workbench.test.ts`

- [ ] **步骤 1：编写失败测试**

在 `admin-workbench.test.ts` 中用字面量 fixture 验证：

```ts
expect(buildLearningLoop({
  questions: 12, diagnoses: 9, sessions: 7,
  cognitive_updates: 5, pending_reviews: 3,
})).toEqual([
  { key: 'questions', label: '错题录入', value: 12, icon: 'camera-filled' },
  { key: 'diagnoses', label: '错因诊断', value: 9, icon: 'search' },
  { key: 'sessions', label: '自适应教学', value: 7, icon: 'chat-filled' },
  { key: 'cognitive_updates', label: '认知更新', value: 5, icon: 'map-filled' },
  { key: 'pending_reviews', label: '主动复习', value: 3, icon: 'calendar-filled' },
])
expect(buildSessionDistribution({ sessions: 10, active_sessions: 4 })).toEqual({
  active: 4, completed: 6, activePercent: 40,
})
```

这个测试要抓住的破坏：错误字段映射、完成会话计算错误或除零导致非法百分比。

- [ ] **步骤 2：运行测试验证失败**

运行：`npm --prefix frontend test -- --run tests/admin-workbench.test.ts`

预期：因 `workbench-data.js` 不存在或导出函数不存在而失败。

- [ ] **步骤 3：实现最小视图模型**

创建纯函数：

```js
export function buildLearningLoop(metrics = {}) {
  return LOOP_DEFINITIONS.map(item => ({ ...item, value: Number(metrics[item.key] || 0) }))
}

export function buildSessionDistribution(metrics = {}) {
  const sessions = Math.max(0, Number(metrics.sessions || 0))
  const active = Math.min(sessions, Math.max(0, Number(metrics.active_sessions || 0)))
  return { active, completed: sessions - active, activePercent: sessions ? Math.round(active / sessions * 100) : 0 }
}
```

- [ ] **步骤 4：运行测试验证通过**

运行：`npm --prefix frontend test -- --run tests/admin-workbench.test.ts`

预期：全部通过。

- [ ] **步骤 5：提交任务**

```bash
git add frontend/src/pages/admin/workbench-data.js frontend/tests/admin-workbench.test.ts
git commit -m "test: 定义管理员图表数据契约"
```

### 任务 2：重写蓝白管理员工作台

**文件：**
- 修改：`frontend/src/pages/admin/workbench.vue`
- 修改：`frontend/tests/admin-workbench.test.ts`

- [ ] **步骤 1：补充页面契约失败测试**

测试读取页面并验证管理员端继续只使用 `getData`，同时要求新的真实功能标题存在、旧工业主题标记消失：

```ts
expect(page).toContain('学习数据闭环')
expect(page).toContain('会话状态分布')
expect(page).toContain('认知变化')
expect(page).toContain("import { getData } from '@/api/index.js'")
expect(page).not.toContain('postData(')
expect(page).not.toContain('--black:')
expect(page).not.toContain('font-family:"SFMono-Regular"')
```

这个测试要抓住的破坏：页面重新退回深色工业主题、丢失核心可视图或引入写请求。

- [ ] **步骤 2：运行测试验证失败**

运行：`npm --prefix frontend test -- --run tests/admin-workbench.test.ts`

预期：因新标题缺失和旧黑色令牌仍存在而失败。

- [ ] **步骤 3：重写模板和脚本**

实现四个模块：

1. 全局概览：指标卡、学习闭环、会话环形图、最近学生和会话。
2. 学生画像：大字号摘要、掌握进度、误区概率、复习计划。
3. 智能体轨迹：会话摘要、诊断卡、可解释步骤、认知变化条。
4. 系统状态：带 `uni-icons` 的白色状态卡和只读说明。

脚本导入 `buildLearningLoop` 和 `buildSessionDistribution`，保留现有三个 GET 请求和 15 秒刷新。

- [ ] **步骤 4：重写 SCSS**

直接使用学生端令牌：`var(--color-primary)`、`var(--color-bg)`、`var(--color-surface)`、`var(--color-text-primary)`、`var(--color-text-secondary)`、`var(--color-border)`。正文不低于 14px，列表标题不低于 15px，页面标题 26px。卡片圆角 18px，导航与卡片均为白色。

- [ ] **步骤 5：运行定向测试与构建**

运行：

```bash
npm --prefix frontend test -- --run tests/admin-workbench.test.ts
npm --prefix frontend run build:h5
```

预期：测试全部通过，构建退出码为 0。

- [ ] **步骤 6：提交任务**

```bash
git add frontend/src/pages/admin/workbench.vue frontend/tests/admin-workbench.test.ts
git commit -m "feat: 重做蓝白管理员工作台"
```

### 任务 3：完整验证和运行验收

**文件：**
- 不新增生产文件

- [ ] **步骤 1：运行完整测试**

```bash
conda run --no-capture-output -n minddimension pytest backend/tests -q
npm --prefix frontend test
conda run --no-capture-output -n minddimension ruff check backend/app backend/tests scripts
npm --prefix frontend run build:h5
```

预期：后端、前端、格式检查和 H5 构建均通过。

- [ ] **步骤 2：真实数据查询验证**

使用管理员登录接口获取本地令牌，通过前端代理请求 `GET /api/v1/admin/workbench`，验证响应包含 `metrics`、`students`、`sessions` 和 `system`，且 HTTP 状态为 200。输出仅显示状态，不打印令牌。

- [ ] **步骤 3：浏览器验收**

确认：页面为蓝白浅色、中文字号清晰、学习闭环和会话环形图显示真实数据、学生和会话可切换、页面没有写操作。

- [ ] **步骤 4：最终状态检查**

运行：`git status --short --branch`

预期：功能提交后工作区干净。
