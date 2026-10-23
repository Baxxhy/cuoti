export const studyEntries = [
  { title: '题库练习', icon: 'compose', tone: 'blue', url: '/pages/bank/bank?mode=practice' },
  { title: '模拟考试', icon: 'medal', tone: 'blue', url: '/pages/bank/bank?mode=exam' },
]
// Each feature has one home; related records are disclosed on demand.
export const learningPrimaryEntries = [
  {
    title: '到期复习',
    description: '回想今天到期的题',
    icon: 'calendar',
    url: '/pages/review/review',
  },
  {
    title: '类似题练习',
    description: '从一道错题开始巩固',
    icon: 'compose',
    url: '/pages/problem/list?purpose=practice',
  },
  {
    title: '错题组卷',
    description: '选题、编排与导出',
    icon: 'download',
    url: '/pages/paper/paper-center',
  },
  {
    title: '知识框架',
    description: '找到概念与前置知识',
    icon: 'wallet',
    url: '/pages/framework/framework',
  },
]
export const learningRecordEntries = [
  { title: '订正记录', url: '/pages/task/task' },
  { title: '复习记录', url: '/pages/review/review?history=1' },
  { title: '重点收藏', url: '/pages/problem/list?favorite=1' },
]
// Shared navigation inventory, also used to validate registered destinations.
export const learningSections = [
  { title: '学习方式', items: [...studyEntries, ...learningPrimaryEntries] },
  {
    title: '记录与任务',
    items: [...learningRecordEntries, { title: '学习报告', url: '/pages/analysis/analysis' }],
  },
]
