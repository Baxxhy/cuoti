<template>
  <view class="admin-page">
    <view class="sidebar">
      <view class="brand">
        <view class="brand-mark">帮</view>
        <view>
          <b>错题帮</b>
          <text>管理工作台</text>
        </view>
      </view>
      <view class="readonly">
        <uni-icons type="info-filled" size="18" color="#2E69FC" />
        <text>只读模式</text>
      </view>
      <view class="nav-list">
        <button
          v-for="item in navItems"
          :key="item.key"
          :class="['nav-item', { active: section === item.key }]"
          @click="section = item.key"
        >
          <uni-icons
            :type="item.icon"
            size="22"
            :color="section === item.key ? '#2E69FC' : '#667085'"
          />
          <text>{{ item.label }}</text>
        </button>
      </view>
      <view class="sidebar-foot">
        <text>数据更新于</text>
        <b>{{ clock(workbench?.generated_at) }}</b>
        <button @click="refresh">
          <uni-icons type="reload" size="18" color="#2E69FC" />
          刷新数据
        </button>
        <button @click="logout">
          <uni-icons type="person-filled" size="18" color="#667085" />
          退出登录
        </button>
      </view>
    </view>

    <view class="main-area">
      <view class="topbar">
        <view>
          <text class="eyebrow">管理员只读工作台</text>
          <text class="page-title">{{ currentTitle }}</text>
          <text class="page-desc">{{ descriptions[section] }}</text>
        </view>
        <view class="service">
          <span :class="serviceClass" />
          <view>
            <b>{{ providerStatus }}</b>
            <text>{{ workbench?.system?.provider?.logical_model || '正在连接服务' }}</text>
          </view>
        </view>
      </view>

      <view v-if="loading && !workbench" class="state">
        <uni-icons type="spinner-cycle" size="44" color="#2E69FC" />
        <b>正在加载工作台</b>
        <text>正在读取学习数据，请稍候</text>
      </view>
      <view v-else-if="error && !workbench" class="state">
        <uni-icons type="info-filled" size="44" color="#D92D20" />
        <b>暂时无法读取数据</b>
        <text>{{ error }}</text>
        <button class="retry" @click="refresh">重新加载</button>
      </view>

      <template v-else-if="workbench">
        <view v-if="error" class="warning">
          <uni-icons type="info-filled" size="18" color="#D97706" />
          <text>{{ error }}，当前展示上次成功读取的数据。</text>
        </view>

        <view v-if="section === 'overview'" class="stack">
          <view class="metric-grid">
            <view v-for="metric in metricCards" :key="metric.key" class="metric-card">
              <view class="icon-box">
                <uni-icons :type="metric.icon" size="24" color="#2E69FC" />
              </view>
              <text>{{ metric.label }}</text>
              <b>{{ metric.value }}</b>
              <small>{{ metric.note }}</small>
            </view>
          </view>

          <view class="overview-grid">
            <view class="card loop-panel">
              <heading title="学习数据闭环" subtitle="从错题录入到主动复习的真实运行数据" />
              <view class="learning-loop">
                <template v-for="(item, index) in learningLoop" :key="item.key">
                  <view class="loop-step">
                    <view><uni-icons :type="item.icon" size="25" color="#2E69FC" /></view>
                    <b>{{ item.value }}</b>
                    <text>{{ item.label }}</text>
                  </view>
                  <view v-if="index < learningLoop.length - 1" class="loop-line">
                    <uni-icons type="arrowright" size="20" color="#AFC8FF" />
                  </view>
                </template>
              </view>
            </view>
            <view class="card distribution-panel">
              <heading title="会话状态分布" subtitle="教学智能体会话完成情况" />
              <view class="distribution">
                <view class="donut" :style="donutStyle">
                  <view>
                    <b>{{ sessionDistribution.activePercent }}%</b>
                    <text>进行中</text>
                  </view>
                </view>
                <view class="legend">
                  <view>
                    <span class="blue" />
                    <text>进行中</text>
                    <b>{{ sessionDistribution.active }}</b>
                  </view>
                  <view>
                    <span />
                    <text>已完成</text>
                    <b>{{ sessionDistribution.completed }}</b>
                  </view>
                </view>
              </view>
            </view>
          </view>

          <view class="overview-grid lower">
            <view class="card">
              <heading title="最近学生" subtitle="点击查看长期学习画像" />
              <view class="table-head">
                <text>学生</text>
                <text>年级</text>
                <text>错题</text>
                <text>会话</text>
              </view>
              <button
                v-for="student in workbench.students.slice(0, 7)"
                :key="student.id"
                class="student-row"
                @click="openStudent(student.id)"
              >
                <view>
                  <span class="avatar">{{ initials(student.name) }}</span>
                  <b>{{ student.name }}</b>
                </view>
                <text>{{ student.grade }}</text>
                <strong>{{ student.question_count }}</strong>
                <strong>{{ student.session_count }}</strong>
              </button>
              <empty-view v-if="!workbench.students.length" text="尚无学生数据" />
            </view>
            <view class="card">
              <heading title="最近教学会话" subtitle="查看智能体如何做出教学决策" />
              <button
                v-for="item in workbench.sessions.slice(0, 7)"
                :key="item.id"
                class="session-row"
                @click="openSession(item.id)"
              >
                <view :class="['session-icon', item.status === 'active' ? 'active' : 'done']">
                  <uni-icons
                    type="chat-filled"
                    size="21"
                    :color="item.status === 'active' ? '#2E69FC' : '#168A45'"
                  />
                </view>
                <view>
                  <b>{{ item.question_title }}</b>
                  <text>{{ item.student_name }} · {{ stageName(item.stage) }}</text>
                </view>
                <small>{{ clock(item.updated_at) }}</small>
                <uni-icons type="right" size="18" color="#98A2B3" />
              </button>
              <empty-view v-if="!workbench.sessions.length" text="尚无教学会话" />
            </view>
          </view>
        </view>

        <view v-else-if="section === 'students'" class="split">
          <view class="card side-list">
            <heading title="学生列表" :subtitle="`共 ${workbench.students.length} 名学生`" />
            <button
              v-for="student in workbench.students"
              :key="student.id"
              :class="['select-row', { selected: selectedStudentId === student.id }]"
              @click="openStudent(student.id)"
            >
              <span class="avatar">{{ initials(student.name) }}</span>
              <view>
                <b>{{ student.name }}</b>
                <text>{{ student.grade }} · {{ student.question_count }} 道错题</text>
              </view>
              <uni-icons type="right" size="18" color="#98A2B3" />
            </button>
            <empty-view v-if="!workbench.students.length" text="尚无学生数据" />
          </view>
          <view class="detail">
            <view v-if="!studentDetail" class="state compact">
              <uni-icons type="person-filled" size="42" color="#AFC8FF" />
              <b>请选择一名学生</b>
              <text>查看知识掌握、常见误区和复习安排</text>
            </view>
            <template v-else>
              <view class="profile">
                <span>{{ initials(studentDetail.student.name) }}</span>
                <view>
                  <text>学生画像</text>
                  <b>{{ studentDetail.student.name }}</b>
                  <p>
                    {{ studentDetail.student.grade }} ·
                    {{ studentDetail.student.learning_goal || '暂未设置学习目标' }}
                  </p>
                </view>
                <view class="profile-metrics">
                  <view>
                    <b>{{ studentDetail.metrics.questions }}</b>
                    <text>错题</text>
                  </view>
                  <view>
                    <b>{{ studentDetail.metrics.sessions }}</b>
                    <text>会话</text>
                  </view>
                  <view>
                    <b>{{ studentDetail.metrics.pending_reviews }}</b>
                    <text>待复习</text>
                  </view>
                </view>
              </view>
              <view class="detail-grid">
                <view class="card">
                  <heading title="知识掌握" subtitle="根据练习证据形成的掌握估计" />
                  <view
                    v-for="item in studentDetail.mastery"
                    :key="`${item.subject}-${item.knowledge_point}`"
                    class="progress-row"
                  >
                    <view>
                      <b>{{ item.knowledge_point }}</b>
                      <text>{{ item.subject }} · {{ item.evidence_count }} 条证据</text>
                    </view>
                    <strong>{{ percent(item.score) }}</strong>
                    <view class="progress"><view :style="{ width: percent(item.score) }" /></view>
                  </view>
                  <empty-view
                    v-if="!studentDetail.mastery.length"
                    text="完成教学后会形成知识掌握记录"
                  />
                </view>
                <view class="card">
                  <heading title="高频误区" subtitle="近期最需要关注的错误模式" />
                  <view
                    v-for="item in studentDetail.misconceptions"
                    :key="item.code"
                    class="risk-row"
                  >
                    <view class="risk-icon">
                      <uni-icons type="info-filled" size="20" color="#D97706" />
                    </view>
                    <view>
                      <b>{{ item.label }}</b>
                      <text>{{ item.evidence_count }} 条学习证据</text>
                      <view class="risk-progress">
                        <view :style="{ width: percent(item.probability) }" />
                      </view>
                    </view>
                    <strong>{{ percent(item.probability) }}</strong>
                  </view>
                  <empty-view
                    v-if="!studentDetail.misconceptions.length"
                    text="目前没有集中出现的误区"
                  />
                </view>
              </view>
              <view class="card">
                <heading title="复习计划" subtitle="系统根据遗忘风险自动安排" />
                <view class="review-grid">
                  <view v-for="item in studentDetail.reviews" :key="item.id" class="review">
                    <view class="calendar">
                      <uni-icons type="calendar-filled" size="22" color="#2E69FC" />
                    </view>
                    <view>
                      <b>{{ item.reason }}</b>
                      <text>{{ fullTime(item.due_at) }}</text>
                    </view>
                    <span>{{ reviewStatus(item.status) }}</span>
                  </view>
                </view>
                <empty-view v-if="!studentDetail.reviews.length" text="暂无复习计划" />
              </view>
            </template>
          </view>
        </view>

        <view v-else-if="section === 'sessions'" class="split sessions-split">
          <view class="card side-list">
            <heading title="教学会话" :subtitle="`最近 ${workbench.sessions.length} 条记录`" />
            <button
              v-for="item in workbench.sessions"
              :key="item.id"
              :class="['select-row', { selected: selectedSessionId === item.id }]"
              @click="openSession(item.id)"
            >
              <view :class="['session-icon', item.status === 'active' ? 'active' : 'done']">
                <uni-icons
                  type="chat-filled"
                  size="19"
                  :color="item.status === 'active' ? '#2E69FC' : '#168A45'"
                />
              </view>
              <view>
                <b>{{ item.question_title }}</b>
                <text>{{ item.student_name }} · {{ stageName(item.stage) }}</text>
              </view>
              <uni-icons type="right" size="18" color="#98A2B3" />
            </button>
            <empty-view v-if="!workbench.sessions.length" text="尚无教学会话" />
          </view>
          <view class="detail">
            <view v-if="!sessionDetail" class="state compact">
              <uni-icons type="chat-filled" size="42" color="#AFC8FF" />
              <b>请选择一个教学会话</b>
              <text>查看智能体的观察、决策、行动和认知更新</text>
            </view>
            <template v-else>
              <view class="summary-grid">
                <view>
                  <text>当前学生</text>
                  <b>{{ sessionDetail.student?.name || '未知学生' }}</b>
                </view>
                <view>
                  <text>当前题目</text>
                  <b>{{ sessionDetail.question?.title || '未命名题目' }}</b>
                </view>
                <view>
                  <text>教学阶段</text>
                  <b>{{ stageName(sessionDetail.session.stage) }}</b>
                </view>
                <view>
                  <text>掌握估计</text>
                  <b class="primary-text">{{ percent(sessionDetail.session.mastery_score) }}</b>
                </view>
              </view>
              <view class="diagnosis">
                <view class="diagnosis-icon">
                  <uni-icons type="search" size="28" color="#2E69FC" />
                </view>
                <view>
                  <text>智能体观察到的错因</text>
                  <b>{{ sessionDetail.diagnosis?.root_misconception || '该会话暂无错因诊断' }}</b>
                  <p>
                    {{ sessionDetail.diagnosis?.first_error_text || '尚未定位具体首错步骤' }}
                  </p>
                </view>
                <view class="strategy">
                  <text>采用的教学策略</text>
                  <b>{{ sessionDetail.diagnosis?.recommended_strategy || '根据对话动态选择' }}</b>
                </view>
              </view>
              <view class="trace-grid">
                <view class="card">
                  <heading
                    title="可验证智能体轨迹"
                    subtitle="观察 → 计划 → 工具行动 → 证据核验，全程不展示模型内部思维链"
                  />
                  <view
                    v-for="(event, index) in sessionDetail.trace"
                    :key="event.id"
                    class="trace-step"
                  >
                    <view class="axis">
                      <span>{{ index + 1 }}</span>
                      <i />
                    </view>
                    <view class="trace-card">
                      <view class="trace-head">
                        <view>
                          <uni-icons type="paperplane-filled" size="20" color="#2E69FC" />
                          <b>{{ event.agent }}</b>
                        </view>
                        <text>{{ clock(event.time) }}</text>
                      </view>
                      <view class="decision">
                        <span>教学决策</span>
                        <b>{{ event.decision }}</b>
                        <em
                          v-if="event.verification?.status"
                          :class="['verify-badge', event.verification.status]"
                        >
                          {{ verificationName(event.verification.status) }}
                        </em>
                      </view>
                      <p>{{ event.goal || '根据当前学习状态推进下一步教学' }}</p>
                      <view
                        v-if="event.observation?.memory_summary"
                        class="agent-block memory-block"
                      >
                        <label>长期记忆</label>
                        <text>{{ event.observation.memory_summary }}</text>
                        <small>{{ event.observation.memory_count || 0 }} 条可追溯证据</small>
                      </view>
                      <view v-if="event.plan?.steps?.length" class="agent-block">
                        <label>执行计划</label>
                        <ol>
                          <li v-for="step in event.plan.steps" :key="step">{{ step }}</li>
                        </ol>
                      </view>
                      <view v-for="action in event.actions" :key="action.id" class="tool">
                        <b>{{ action.tool }}</b>
                        <text>{{ compactJson(action.output) }}</text>
                      </view>
                      <view v-if="event.verification?.evidence_refs?.length" class="evidence">
                        <uni-icons type="checkbox-filled" size="17" color="#168A45" />
                        <text>证据：{{ event.verification.evidence_refs.join(' · ') }}</text>
                      </view>
                    </view>
                  </view>
                  <empty-view v-if="!sessionDetail.trace.length" text="该会话尚未记录智能体轨迹" />
                </view>
                <view class="card cognition">
                  <heading title="认知变化" subtitle="本次学习对长期认知状态的影响" />
                  <view
                    v-for="item in sessionDetail.cognitive_updates"
                    :key="item.id"
                    class="cognition-row"
                  >
                    <view>
                      <b>{{ item.entity_key }}</b>
                      <span :class="item.new_value >= item.old_value ? 'up' : 'down'">
                        {{ signedDelta(item) }}
                      </span>
                    </view>
                    <text>{{ item.reason || '认知状态变化' }}</text>
                    <view class="compare-label">
                      <span>学习前 {{ percent(item.old_value) }}</span>
                      <span>学习后 {{ percent(item.new_value) }}</span>
                    </view>
                    <view class="compare">
                      <view class="before" :style="{ width: percent(item.old_value) }" />
                      <view class="after" :style="{ width: percent(item.new_value) }" />
                    </view>
                  </view>
                  <empty-view
                    v-if="!sessionDetail.cognitive_updates.length"
                    text="该会话暂无认知更新"
                  />
                </view>
              </view>
            </template>
          </view>
        </view>

        <view v-else class="system-grid">
          <view v-for="item in systemCards" :key="item.label" class="system-card">
            <view :class="['system-icon', item.tone]">
              <uni-icons :type="item.icon" size="28" :color="item.color" />
            </view>
            <text>{{ item.label }}</text>
            <b>{{ item.value }}</b>
            <span>{{ item.status }}</span>
          </view>
          <view class="card access">
            <view><uni-icons type="info-filled" size="28" color="#2E69FC" /></view>
            <view>
              <b>只读访问</b>
              <p>工作台只查询学生学习数据，不修改答案、诊断、教学会话、认知模型或系统配置。</p>
              <text>敏感字段和模型内部推理不会进入工作台响应。</text>
            </view>
          </view>
        </view>
      </template>
    </view>
  </view>
</template>

<script setup>
import { computed, defineComponent, h, onMounted, onUnmounted, ref } from 'vue'
import { getData } from '@/api/index.js'
import { roleHome, useAppStore } from '@/store/index.js'
import { buildLearningLoop, buildSessionDistribution } from './workbench-data.js'

const Heading = defineComponent({
  props: ['title', 'subtitle'],
  setup: (p) => () => h('view', { class: 'heading' }, [h('b', p.title), h('text', p.subtitle)]),
})
const EmptyView = defineComponent({
  props: ['text'],
  setup: (p) => () => h('view', { class: 'empty' }, p.text),
})
const store = useAppStore(),
  section = ref('overview'),
  workbench = ref(null),
  studentDetail = ref(null),
  sessionDetail = ref(null),
  selectedStudentId = ref(''),
  selectedSessionId = ref(''),
  loading = ref(false),
  error = ref('')
let timer
const navItems = [
  { key: 'overview', label: '全局概览', icon: 'bars' },
  { key: 'students', label: '学生画像', icon: 'person-filled' },
  { key: 'sessions', label: '智能体轨迹', icon: 'chat-filled' },
  { key: 'system', label: '系统状态', icon: 'gear-filled' },
]
const descriptions = {
  overview: '了解系统中的学习数据和智能体运行情况',
  students: '查看每位学生的长期学习状态',
  sessions: '查看教学智能体如何观察并做出决策',
  system: '查看模型、线路和数据服务状态',
}
const currentTitle = computed(
  () => navItems.find((i) => i.key === section.value)?.label || '管理工作台',
)
const metricCards = computed(() => [
  {
    key: 'students',
    label: '学生人数',
    value: workbench.value.metrics.students,
    note: '已建立学习画像',
    icon: 'person-filled',
  },
  {
    key: 'questions',
    label: '有效错题',
    value: workbench.value.metrics.questions,
    note: '进入诊断流程',
    icon: 'camera-filled',
  },
  {
    key: 'diagnoses',
    label: '错因诊断',
    value: workbench.value.metrics.diagnoses,
    note: '已完成分析',
    icon: 'search',
  },
  {
    key: 'active_sessions',
    label: '进行中会话',
    value: workbench.value.metrics.active_sessions,
    note: '正在自适应教学',
    icon: 'chat-filled',
  },
  {
    key: 'agent_runs',
    label: '智能体执行',
    value: workbench.value.metrics.agent_runs,
    note: '可解释运行记录',
    icon: 'paperplane-filled',
  },
  {
    key: 'pending_reviews',
    label: '待复习任务',
    value: workbench.value.metrics.pending_reviews,
    note: '主动防错安排',
    icon: 'calendar-filled',
  },
])
const learningLoop = computed(() => buildLearningLoop(workbench.value?.metrics)),
  sessionDistribution = computed(() => buildSessionDistribution(workbench.value?.metrics))
const donutStyle = computed(() => ({
  background: `conic-gradient(var(--color-primary) 0 ${sessionDistribution.value.activePercent * 3.6}deg,#E8EEFC ${sessionDistribution.value.activePercent * 3.6}deg 360deg)`,
}))
const providerStatus = computed(
    () =>
      ({ ok: '运行正常', ready: '运行正常', degraded: '服务降级' })[
        workbench.value?.system?.provider?.status
      ] || '等待调用',
  ),
  serviceClass = computed(() =>
    workbench.value?.system?.provider?.status === 'degraded' ? 'warning' : 'success',
  )
const systemCards = computed(() => [
  {
    label: '数据存储',
    value: workbench.value.system.database,
    status: '连接正常',
    icon: 'checkbox-filled',
    tone: 'success',
    color: '#168A45',
  },
  {
    label: '逻辑模型',
    value: workbench.value.system.provider.logical_model,
    status: providerStatus.value,
    icon: 'chat-filled',
    tone: 'primary',
    color: '#2E69FC',
  },
  {
    label: '文本线路',
    value: workbench.value.system.provider.text_entries,
    status: '可用线路',
    icon: 'paperplane-filled',
    tone: 'primary',
    color: '#2E69FC',
  },
  {
    label: '视觉线路',
    value: workbench.value.system.provider.vision_entries,
    status: '可用线路',
    icon: 'image',
    tone: 'primary',
    color: '#2E69FC',
  },
])
const percent = (v) => `${Math.round(Math.max(0, Math.min(1, Number(v || 0))) * 100)}%`,
  initials = (n) => String(n || '学').slice(0, 1),
  stageName = (s) =>
    ({
      understanding: '理解确认',
      diagnosis: '错因诊断',
      teaching: '针对教学',
      practice: '迁移练习',
      review: '复习巩固',
    })[s] ||
    s ||
    '未开始'
const clock = (v) =>
    v
      ? new Date(v).toLocaleString('zh-CN', {
          month: '2-digit',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit',
        })
      : '--',
  fullTime = (v) =>
    v
      ? new Date(v).toLocaleString('zh-CN', {
          year: 'numeric',
          month: '2-digit',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit',
        })
      : '时间未设置'
const compactJson = (v) => {
    const t = JSON.stringify(v || {})
    return t.length > 100 ? `${t.slice(0, 100)}…` : t
  },
  reviewStatus = (s) => ({ pending: '待完成', completed: '已完成', overdue: '已逾期' })[s] || s,
  signedDelta = (i) => {
    const d = Math.round((Number(i.new_value) - Number(i.old_value)) * 100)
    return `${d >= 0 ? '+' : ''}${d}%`
  }
const verificationName = (s) =>
  ({ verified: '证据已核验', partial: '部分可验证', rejected: '执行未通过' })[s] || s
async function refresh() {
  loading.value = true
  error.value = ''
  try {
    workbench.value = await getData('/admin/workbench')
  } catch (e) {
    error.value = e?.message || '连接失败'
  } finally {
    loading.value = false
  }
}
async function openStudent(id) {
  selectedStudentId.value = id
  section.value = 'students'
  try {
    studentDetail.value = await getData(`/admin/students/${id}`)
  } catch (e) {
    error.value = e?.message || '学生画像加载失败'
  }
}
async function openSession(id) {
  selectedSessionId.value = id
  section.value = 'sessions'
  try {
    sessionDetail.value = await getData(`/admin/sessions/${id}`)
  } catch (e) {
    error.value = e?.message || '教学会话加载失败'
  }
}
function logout() {
  store.logout()
}
onMounted(async () => {
  await store.loadUser()
  if (store.role !== 'admin') {
    uni.reLaunch({ url: roleHome(store.role) })
    return
  }
  await refresh()
  timer = setInterval(refresh, 15000)
})
onUnmounted(() => clearInterval(timer))
</script>

<style scoped lang="scss">
:global(body) {
  margin: 0;
  background: var(--color-bg);
}
.admin-page {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 248px minmax(0, 1fr);
  background: var(--color-bg);
  color: var(--color-text-primary);
  font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif;
}
.sidebar {
  position: sticky;
  top: 0;
  height: 100vh;
  padding: 28px 20px;
  background: #fff;
  border-right: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
}
.brand {
  display: flex;
  align-items: center;
  gap: 13px;
  padding: 0 8px 26px;
  border-bottom: 1px solid var(--color-border);
}
.brand-mark {
  width: 46px;
  height: 46px;
  border-radius: 14px;
  background: var(--color-primary);
  color: #fff;
  font-size: 24px;
  font-weight: 700;
  display: grid;
  place-items: center;
}
.brand b,
.brand text {
  display: block;
}
.brand b {
  font-size: 19px;
}
.brand text {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin-top: 3px;
}
.readonly {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 20px 8px 12px;
  padding: 10px 12px;
  border-radius: 12px;
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-size: 14px;
  font-weight: 600;
}
.nav-list {
  display: flex;
  flex-direction: column;
  gap: 7px;
}
.nav-item,
.sidebar-foot button,
.student-row,
.session-row,
.select-row {
  border: 0;
  background: transparent;
  font: inherit;
  cursor: pointer;
}
.nav-item {
  height: 50px;
  border-radius: 14px;
  padding: 0 14px;
  display: flex;
  align-items: center;
  gap: 13px;
  color: var(--color-text-secondary);
  font-size: 15px;
}
.nav-item.active {
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-weight: 650;
}
.sidebar-foot {
  margin-top: auto;
  border-top: 1px solid var(--color-border);
  padding: 18px 8px 0;
}
.sidebar-foot > text,
.sidebar-foot > b {
  display: block;
}
.sidebar-foot > text {
  font-size: 13px;
  color: var(--color-text-tertiary);
}
.sidebar-foot > b {
  font-size: 14px;
  margin: 5px 0 12px;
}
.sidebar-foot button {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 9px 0;
  color: var(--color-text-secondary);
  font-size: 14px;
}
.main-area {
  min-width: 0;
  padding: 0 34px 48px;
}
.topbar {
  min-height: 112px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--color-border);
  margin-bottom: 26px;
}
.eyebrow,
.page-title,
.page-desc {
  display: block;
}
.eyebrow {
  font-size: 14px;
  color: var(--color-primary);
  font-weight: 600;
}
.page-title {
  font-size: 28px;
  font-weight: 700;
  margin-top: 5px;
}
.page-desc {
  font-size: 15px;
  color: var(--color-text-secondary);
  margin-top: 5px;
}
.service {
  min-width: 210px;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-radius: 16px;
  background: #fff;
  border: 1px solid var(--color-border);
}
.service > span {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--color-success);
}
.service > span.warning {
  background: var(--color-warning);
}
.service b,
.service text {
  display: block;
}
.service b {
  font-size: 15px;
}
.service text {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin-top: 2px;
}
.stack,
.detail {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.metric-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 14px;
}
.metric-card,
.system-card {
  padding: 20px;
  background: #fff;
  border: 1px solid var(--color-border);
  border-radius: 18px;
}
.icon-box,
.system-icon {
  width: 42px;
  height: 42px;
  border-radius: 13px;
  background: var(--color-primary-soft);
  display: grid;
  place-items: center;
  margin-bottom: 16px;
}
.metric-card > text,
.metric-card > b,
.metric-card > small {
  display: block;
}
.metric-card > text {
  font-size: 14px;
  color: var(--color-text-secondary);
}
.metric-card > b {
  font-size: 30px;
  margin-top: 4px;
}
.metric-card > small {
  font-size: 13px;
  color: var(--color-text-tertiary);
  margin-top: 5px;
}
.card {
  background: #fff;
  border: 1px solid var(--color-border);
  border-radius: 18px;
  overflow: hidden;
  min-width: 0;
}
.heading {
  padding: 21px 23px 17px;
  border-bottom: 1px solid var(--color-border);
}
.heading b,
.heading text {
  display: block;
}
.heading b {
  font-size: 19px;
}
.heading text {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin-top: 5px;
}
.overview-grid {
  display: grid;
  grid-template-columns: 1.65fr 0.7fr;
  gap: 20px;
}
.overview-grid.lower {
  grid-template-columns: 1fr 1fr;
}
.learning-loop {
  min-height: 190px;
  padding: 28px 22px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.loop-step {
  min-width: 90px;
  text-align: center;
}
.loop-step > view {
  width: 54px;
  height: 54px;
  border-radius: 17px;
  background: var(--color-primary-soft);
  display: grid;
  place-items: center;
  margin: 0 auto 9px;
}
.loop-step b,
.loop-step text {
  display: block;
}
.loop-step b {
  font-size: 22px;
}
.loop-step text {
  font-size: 14px;
  color: var(--color-text-secondary);
}
.loop-line {
  flex: 1;
  height: 2px;
  background: #dce6ff;
  position: relative;
  margin: 0 4px 45px;
}
.loop-line :deep(.uni-icons) {
  position: absolute;
  right: -4px;
  top: -11px;
  background: #fff;
}
.distribution {
  min-height: 190px;
  padding: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 28px;
}
.donut {
  width: 132px;
  height: 132px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  position: relative;
}
.donut:after {
  content: '';
  position: absolute;
  inset: 18px;
  border-radius: 50%;
  background: #fff;
}
.donut > view {
  position: relative;
  z-index: 1;
  text-align: center;
}
.donut b,
.donut text {
  display: block;
}
.donut b {
  font-size: 27px;
}
.donut text {
  font-size: 13px;
  color: var(--color-text-secondary);
}
.legend > view {
  display: grid;
  grid-template-columns: 10px 1fr auto;
  gap: 8px;
  align-items: center;
  margin: 14px 0;
  font-size: 14px;
}
.legend span {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #dde7ff;
}
.legend span.blue {
  background: var(--color-primary);
}
.legend text {
  color: var(--color-text-secondary);
}
.table-head,
.student-row {
  display: grid;
  grid-template-columns: 1.5fr 0.7fr 0.5fr 0.5fr;
  align-items: center;
  padding: 0 22px;
}
.table-head {
  height: 42px;
  background: #fafbfc;
  border-bottom: 1px solid var(--color-border);
  font-size: 13px;
  color: var(--color-text-secondary);
}
.student-row {
  width: 100%;
  height: 62px;
  border-bottom: 1px solid var(--color-border);
  font-size: 14px;
  text-align: left;
  color: inherit;
}
.student-row > view {
  display: flex;
  align-items: center;
  gap: 10px;
}
.student-row strong {
  text-align: center;
}
.avatar {
  width: 36px;
  height: 36px;
  border-radius: 12px;
  background: var(--color-primary-soft);
  color: var(--color-primary);
  display: grid;
  place-items: center;
  font-size: 15px;
  font-weight: 700;
}
.session-row {
  width: 100%;
  min-height: 62px;
  padding: 10px 20px;
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr) auto 20px;
  gap: 11px;
  align-items: center;
  border-bottom: 1px solid var(--color-border);
  text-align: left;
  color: inherit;
}
.session-icon {
  width: 40px;
  height: 40px;
  border-radius: 13px;
  background: var(--color-primary-soft);
  display: grid;
  place-items: center;
}
.session-icon.done {
  background: var(--color-success-soft);
}
.session-row b,
.session-row text {
  display: block;
}
.session-row b,
.select-row b {
  font-size: 15px;
}
.session-row text,
.session-row small,
.select-row text {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin-top: 3px;
}
.empty {
  padding: 40px 20px;
  text-align: center;
  font-size: 14px;
  color: var(--color-text-secondary);
}
.state {
  min-height: 55vh;
  border: 1px solid var(--color-border);
  border-radius: 18px;
  background: #fff;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
}
.state b {
  font-size: 20px;
  margin-top: 14px;
}
.state text {
  font-size: 15px;
  color: var(--color-text-secondary);
  margin-top: 7px;
}
.state.compact {
  min-height: 280px;
}
.retry {
  margin-top: 18px;
  border: 0;
  border-radius: 12px;
  background: var(--color-primary);
  color: #fff;
  padding: 12px 22px;
  font-size: 15px;
}
.warning {
  display: flex;
  gap: 9px;
  align-items: center;
  padding: 12px 16px;
  margin-bottom: 18px;
  border-radius: 14px;
  background: var(--color-warning-soft);
  color: #9a6416;
  font-size: 14px;
}
.split {
  display: grid;
  grid-template-columns: 310px minmax(0, 1fr);
  gap: 20px;
  align-items: start;
}
.side-list {
  position: sticky;
  top: 24px;
  max-height: calc(100vh - 150px);
  overflow: auto;
}
.select-row {
  width: 100%;
  min-height: 68px;
  padding: 12px 18px;
  display: grid;
  grid-template-columns: 40px minmax(0, 1fr) 20px;
  gap: 11px;
  align-items: center;
  border-bottom: 1px solid var(--color-border);
  text-align: left;
  color: inherit;
}
.select-row.selected {
  background: var(--color-primary-soft);
  box-shadow: inset 3px 0 var(--color-primary);
}
.select-row b,
.select-row text {
  display: block;
}
.profile {
  padding: 26px;
  border-radius: 20px;
  background: linear-gradient(135deg, #2e69fc, #1746b3);
  color: #fff;
  display: flex;
  align-items: center;
  gap: 18px;
}
.profile > span {
  width: 64px;
  height: 64px;
  border-radius: 20px;
  background: #ffffff2e;
  display: grid;
  place-items: center;
  font-size: 27px;
  font-weight: 700;
}
.profile > view:nth-child(2) {
  flex: 1;
}
.profile > view > text,
.profile > view > b {
  display: block;
}
.profile > view > b {
  font-size: 25px;
}
.profile p {
  font-size: 14px;
  margin: 5px 0;
}
.profile-metrics {
  display: flex;
}
.profile-metrics > view {
  min-width: 80px;
  padding: 7px 16px;
  text-align: center;
  border-left: 1px solid #ffffff45;
}
.profile-metrics b {
  font-size: 23px;
}
.profile-metrics text {
  font-size: 13px;
}
.detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}
.progress-row {
  padding: 18px 22px;
  border-bottom: 1px solid var(--color-border);
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 10px;
}
.progress-row b,
.progress-row text {
  display: block;
}
.progress-row b,
.risk-row b {
  font-size: 15px;
}
.progress-row text,
.risk-row text {
  font-size: 13px;
  color: var(--color-text-secondary);
}
.progress-row strong {
  color: var(--color-primary);
}
.progress,
.risk-progress {
  grid-column: 1/-1;
  height: 9px;
  border-radius: 9px;
  background: #e8edf5;
  overflow: hidden;
}
.progress > view {
  height: 100%;
  background: var(--color-primary);
}
.risk-row {
  padding: 16px 20px;
  display: grid;
  grid-template-columns: 38px minmax(0, 1fr) auto;
  gap: 11px;
  align-items: center;
  border-bottom: 1px solid var(--color-border);
}
.risk-icon,
.calendar {
  width: 38px;
  height: 38px;
  border-radius: 12px;
  background: var(--color-warning-soft);
  display: grid;
  place-items: center;
}
.risk-progress {
  grid-column: auto;
  height: 7px;
  margin-top: 8px;
}
.risk-progress > view {
  height: 100%;
  background: var(--color-warning);
}
.risk-row strong {
  color: #9a6416;
}
.review-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  padding: 20px;
}
.review {
  display: grid;
  grid-template-columns: 42px 1fr auto;
  gap: 11px;
  align-items: center;
  padding: 15px;
  border: 1px solid var(--color-border);
  border-radius: 14px;
}
.calendar {
  background: var(--color-primary-soft);
}
.review b,
.review text {
  display: block;
}
.review b {
  font-size: 14px;
}
.review text {
  font-size: 13px;
  color: var(--color-text-secondary);
}
.review > span {
  padding: 5px 9px;
  border-radius: 99px;
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-size: 12px;
}
.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
}
.summary-grid > view {
  padding: 18px 20px;
  border-radius: 17px;
  background: #fff;
  border: 1px solid var(--color-border);
}
.summary-grid text,
.summary-grid b {
  display: block;
}
.summary-grid text {
  font-size: 13px;
  color: var(--color-text-secondary);
}
.summary-grid b {
  font-size: 16px;
  margin-top: 7px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.primary-text {
  color: var(--color-primary);
}
.diagnosis {
  padding: 22px;
  border: 1px solid var(--color-primary-border);
  border-radius: 18px;
  background: var(--color-primary-soft);
  display: grid;
  grid-template-columns: 52px minmax(0, 1fr) minmax(210px, 0.45fr);
  gap: 16px;
  align-items: center;
}
.diagnosis-icon {
  width: 50px;
  height: 50px;
  border-radius: 16px;
  background: #fff;
  display: grid;
  place-items: center;
}
.diagnosis text,
.diagnosis b {
  display: block;
}
.diagnosis text {
  font-size: 13px;
  color: var(--color-primary);
}
.diagnosis b {
  font-size: 17px;
  margin-top: 5px;
}
.diagnosis p {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin: 6px 0;
}
.strategy {
  padding-left: 18px;
  border-left: 1px solid var(--color-primary-border);
}
.strategy b {
  font-size: 15px;
}
.trace-grid {
  display: grid;
  grid-template-columns: 1.5fr 0.7fr;
  gap: 20px;
  align-items: start;
}
.trace-step {
  display: grid;
  grid-template-columns: 48px 1fr;
  padding: 20px 22px 0;
}
.axis {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.axis span {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--color-primary);
  color: #fff;
  display: grid;
  place-items: center;
  font-size: 14px;
}
.axis i {
  width: 2px;
  flex: 1;
  background: #dce6ff;
}
.trace-card {
  padding: 18px;
  margin-bottom: 18px;
  border: 1px solid var(--color-border);
  border-radius: 16px;
}
.trace-head,
.trace-head > view,
.decision,
.cognition-row > view,
.compare-label {
  display: flex;
  align-items: center;
}
.trace-head,
.cognition-row > view,
.compare-label {
  justify-content: space-between;
}
.trace-head > view,
.decision {
  gap: 8px;
}
.trace-head b {
  font-size: 16px;
}
.trace-head > text {
  font-size: 13px;
  color: var(--color-text-secondary);
}
.decision {
  margin-top: 14px;
  flex-wrap: wrap;
}
.decision span {
  padding: 5px 9px;
  border-radius: 99px;
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-size: 12px;
}
.decision b {
  font-size: 15px;
}
.verify-badge {
  margin-left: auto;
  padding: 5px 9px;
  border-radius: 99px;
  background: var(--color-success-soft);
  color: var(--color-success);
  font-size: 12px;
  font-style: normal;
}
.verify-badge.partial {
  background: var(--color-warning-soft);
  color: #9a6416;
}
.verify-badge.rejected {
  background: #fee4e2;
  color: var(--color-error);
}
.trace-card p,
.tool text {
  font-size: 14px;
  color: var(--color-text-secondary);
}
.agent-block {
  padding: 13px 14px;
  border-radius: 12px;
  background: #f8fafc;
  margin-top: 10px;
}
.agent-block label,
.agent-block text,
.agent-block small {
  display: block;
}
.agent-block label {
  font-size: 12px;
  color: var(--color-primary);
  font-weight: 650;
}
.agent-block text {
  font-size: 14px;
  margin-top: 5px;
}
.agent-block small {
  font-size: 12px;
  color: var(--color-text-tertiary);
  margin-top: 4px;
}
.agent-block ol {
  padding-left: 20px;
  margin: 7px 0 0;
}
.agent-block li {
  font-size: 13px;
  line-height: 1.8;
  color: var(--color-text-secondary);
}
.memory-block {
  background: var(--color-primary-soft);
}
.tool {
  padding: 12px 14px;
  border-radius: 12px;
  background: var(--color-bg);
  margin-top: 10px;
}
.tool b,
.tool text {
  display: block;
}
.tool b {
  font-size: 14px;
}
.tool text {
  font-size: 13px;
  word-break: break-all;
}
.evidence {
  display: flex;
  align-items: flex-start;
  gap: 7px;
  margin-top: 11px;
  padding: 10px 12px;
  border-radius: 11px;
  background: var(--color-success-soft);
  color: #116b38;
}
.evidence text {
  font-size: 12px;
  line-height: 1.55;
  word-break: break-all;
}
.cognition {
  position: sticky;
  top: 24px;
}
.cognition-row {
  padding: 18px 20px;
  border-bottom: 1px solid var(--color-border);
}
.cognition-row b {
  font-size: 15px;
}
.cognition-row .up {
  color: var(--color-success);
}
.cognition-row .down {
  color: var(--color-error);
}
.cognition-row > text {
  display: block;
  font-size: 13px;
  color: var(--color-text-secondary);
  margin-top: 5px;
}
.compare-label {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-top: 14px;
}
.compare {
  height: 11px;
  border-radius: 10px;
  background: #e8edf5;
  position: relative;
  margin-top: 7px;
  overflow: hidden;
}
.compare view {
  position: absolute;
  left: 0;
  height: 100%;
}
.compare .before {
  background: #b8c3d5;
}
.compare .after {
  height: 5px;
  top: 3px;
  background: var(--color-primary);
}
.system-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
}
.system-card > text,
.system-card > b,
.system-card > span {
  display: block;
}
.system-icon.success {
  background: var(--color-success-soft);
}
.system-icon.warning {
  background: var(--color-warning-soft);
}
.system-card > text {
  font-size: 14px;
  color: var(--color-text-secondary);
}
.system-card > b {
  font-size: 20px;
  margin-top: 6px;
  overflow-wrap: anywhere;
}
.system-card > span {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin-top: 8px;
}
.access {
  grid-column: 1/-1;
  padding: 24px;
  display: flex;
  gap: 16px;
}
.access > view:first-child {
  width: 50px;
  height: 50px;
  flex: none;
  border-radius: 16px;
  background: var(--color-primary-soft);
  display: grid;
  place-items: center;
}
.access b {
  font-size: 18px;
}
.access p,
.access text {
  display: block;
  font-size: 14px;
  line-height: 1.7;
  color: var(--color-text-secondary);
  margin: 6px 0;
}
@media (max-width: 1250px) {
  .metric-grid {
    grid-template-columns: repeat(3, 1fr);
  }
  .overview-grid,
  .overview-grid.lower {
    grid-template-columns: 1fr;
  }
  .trace-grid {
    grid-template-columns: 1fr;
  }
  .cognition {
    position: static;
  }
  .system-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
@media (max-width: 900px) {
  .admin-page {
    grid-template-columns: 88px 1fr;
  }
  .sidebar {
    padding: 22px 12px;
  }
  .brand {
    justify-content: center;
  }
  .brand > view:last-child,
  .readonly text,
  .nav-item text,
  .sidebar-foot {
    display: none;
  }
  .readonly,
  .nav-item {
    justify-content: center;
  }
  .main-area {
    padding: 0 20px 36px;
  }
  .service {
    display: none;
  }
  .split {
    grid-template-columns: 250px 1fr;
  }
  .detail-grid,
  .summary-grid {
    grid-template-columns: 1fr 1fr;
  }
  .profile-metrics {
    display: none;
  }
  .system-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 600px) {
  .admin-page {
    display: block;
    width: 100%;
    min-width: 0;
  }
  .sidebar {
    position: static;
    height: auto;
    padding: 16px 20px 12px;
    border-right: 0;
    border-bottom: 1px solid var(--color-border);
  }
  .brand {
    justify-content: flex-start;
    padding: 0 0 12px;
    border: 0;
  }
  .brand > view:last-child {
    display: block;
  }
  .brand-mark {
    width: 36px;
    height: 36px;
    font-size: 20px;
    border-radius: 8px;
  }
  .brand b {
    font-size: 17px;
  }
  .brand text {
    font-size: 12px;
  }
  .readonly {
    display: none;
  }
  .nav-list {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 4px;
  }
  .nav-item {
    height: auto;
    min-height: 58px;
    padding: 8px 2px;
    flex-direction: column;
    gap: 4px;
    border-radius: 7px;
    font-size: 12px;
    line-height: 1.4;
  }
  .nav-item text {
    display: block;
    white-space: nowrap;
  }
  .sidebar-foot {
    display: flex;
    justify-content: flex-end;
    gap: 18px;
    margin: 8px 0 0;
    padding: 0;
    border: 0;
  }
  .sidebar-foot > text,
  .sidebar-foot > b {
    display: none;
  }
  .sidebar-foot button {
    margin: 0;
    padding: 6px 0;
    min-height: 36px;
    font-size: 12px;
  }
  .main-area {
    padding: 0 20px 32px;
  }
  .topbar {
    min-height: 0;
    padding: 20px 0;
    margin-bottom: 20px;
  }
  .eyebrow {
    font-size: 12px;
  }
  .page-title {
    font-size: 22px;
  }
  .page-desc {
    font-size: 13px;
    line-height: 1.6;
  }
  .metric-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
  }
  .metric-card,
  .system-card {
    padding: 14px;
    border-radius: 10px;
    min-width: 0;
  }
  .icon-box,
  .system-icon {
    width: 32px;
    height: 32px;
    margin-bottom: 10px;
    border-radius: 7px;
  }
  .metric-card > b {
    font-size: 26px;
  }
  .metric-card > text,
  .metric-card > small {
    font-size: 12px;
  }
  .heading {
    padding: 16px;
  }
  .heading b {
    font-size: 17px;
  }
  .heading text {
    font-size: 12px;
    line-height: 1.6;
  }
  .learning-loop {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 18px 8px;
    padding: 20px 12px;
  }
  .loop-step {
    min-width: 0;
  }
  .loop-step > view {
    width: 40px;
    height: 40px;
    border-radius: 8px;
  }
  .loop-step text {
    font-size: 12px;
  }
  .loop-line {
    display: none;
  }
  .distribution {
    padding: 20px 12px;
    gap: 18px;
  }
  .table-head,
  .student-row {
    grid-template-columns: minmax(0, 1fr) 46px 32px 32px;
    padding-left: 12px;
    padding-right: 12px;
    font-size: 12px;
  }
  .student-row > view,
  .session-row > view,
  .select-row > view {
    min-width: 0;
  }
  .student-row > view {
    gap: 7px;
  }
  .student-row b {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .avatar {
    width: 28px;
    height: 28px;
    flex: none;
    font-size: 12px;
    border-radius: 7px;
  }
  .session-row {
    grid-template-columns: 32px minmax(0, 1fr) 42px 18px;
    gap: 8px;
    padding: 12px;
  }
  .session-row b {
    font-size: 13px;
    line-height: 1.5;
  }
  .session-row text,
  .session-row small {
    font-size: 11px;
  }
  .session-icon {
    width: 30px;
    height: 30px;
  }
  .split,
  .sessions-split,
  .detail-grid,
  .trace-grid {
    grid-template-columns: minmax(0, 1fr);
  }
  .side-list {
    max-height: 300px;
    overflow-y: auto;
  }
  .select-row {
    padding: 12px;
  }
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .profile {
    padding: 14px;
    gap: 12px;
  }
  .profile > span {
    width: 42px;
    height: 42px;
    flex: none;
  }
  .diagnosis {
    padding: 16px;
    grid-template-columns: 38px minmax(0, 1fr);
  }
  .diagnosis-icon {
    width: 36px;
    height: 36px;
  }
  .strategy {
    grid-column: 1 / -1;
    padding: 12px 0 0;
    border-left: 0;
    border-top: 1px solid var(--color-primary-border);
  }
  .review-grid {
    grid-template-columns: minmax(0, 1fr);
    padding: 14px;
  }
  .trace-step {
    grid-template-columns: 32px minmax(0, 1fr);
    padding: 16px 12px 0;
  }
  .trace-card {
    padding: 12px;
  }
  .trace-head {
    align-items: flex-start;
    gap: 8px;
    flex-wrap: wrap;
  }
  .trace-head b {
    font-size: 14px;
  }
  .access {
    padding: 16px;
    gap: 12px;
  }
  .access > view:first-child {
    width: 36px;
    height: 36px;
  }
}
</style>
