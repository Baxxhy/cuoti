<template>
  <div class="admin-page">
    <div class="sidebar">
      <div class="brand">
        <div class="brand-mark">帮</div>
        <div>
          <b>错题帮</b>
          <span>管理工作台</span>
        </div>
      </div>
      <div class="readonly">
        <WebIcon aria-hidden="true" type="info-filled" size="18" color="var(--color-primary)" />
        <span>只读模式</span>
      </div>
      <div class="nav-list">
        <button
          role="button"
          v-for="item in navItems"
          :key="item.key"
          :class="['nav-item', { active: section === item.key }]"
          @click="section = item.key"
        >
          <WebIcon
            aria-hidden="true"
            :type="item.icon"
            size="22"
            :color="section === item.key ? 'var(--color-primary)' : 'var(--color-text-secondary)'"
          />
          <span>{{ item.label }}</span>
        </button>
      </div>
      <div class="sidebar-foot">
        <span>数据更新于</span>
        <b>{{ clock(workbench?.generated_at) }}</b>
        <button role="button" @click="refresh">
          <WebIcon aria-hidden="true" type="reload" size="18" color="var(--color-primary)" />
          刷新数据
        </button>
        <button role="button" @click="logout">
          <WebIcon
            aria-hidden="true"
            type="person-filled"
            size="18"
            color="var(--color-text-secondary)"
          />
          退出登录
        </button>
      </div>
    </div>

    <div class="main-area">
      <div class="topbar">
        <div>
          <component :is="'h1'" class="page-title">{{ currentTitle }}</component>
        </div>
        <div class="service">
          <span :class="serviceClass" />
          <div>
            <b>{{ providerStatus }}</b>
            <span>{{ workbench?.system?.provider?.logical_model || '正在连接服务' }}</span>
          </div>
        </div>
      </div>

      <div v-if="loading && !workbench" class="state">
        <WebIcon aria-hidden="true" type="spinner-cycle" size="44" color="var(--color-primary)" />
        <b>正在加载工作台</b>
        <span>正在读取学习数据，请稍候</span>
      </div>
      <div v-else-if="error && !workbench" class="state">
        <WebIcon aria-hidden="true" type="info-filled" size="44" color="#D92D20" />
        <b>暂时无法读取数据</b>
        <span>{{ error }}</span>
        <button role="button" class="retry" @click="refresh">重新加载</button>
      </div>

      <template v-else-if="workbench">
        <div v-if="error" class="warning">
          <WebIcon aria-hidden="true" type="info-filled" size="18" color="#D97706" />
          <span>{{ error }}，当前展示上次成功读取的数据。</span>
        </div>

        <div v-if="section === 'overview'" class="stack">
          <div class="metric-grid">
            <div v-for="metric in metricCards" :key="metric.key" class="metric-card">
              <div class="icon-box">
                <WebIcon
                  aria-hidden="true"
                  :type="metric.icon"
                  size="24"
                  color="var(--color-primary)"
                />
              </div>
              <span>{{ metric.label }}</span>
              <b>{{ metric.value }}</b>
              <small>{{ metric.note }}</small>
            </div>
          </div>

          <div class="overview-grid">
            <div class="card loop-panel">
              <heading title="学习数据闭环" />
              <div class="learning-loop">
                <template v-for="(item, index) in learningLoop" :key="item.key">
                  <div class="loop-step">
                    <div>
                      <WebIcon
                        aria-hidden="true"
                        :type="item.icon"
                        size="25"
                        color="var(--color-primary)"
                      />
                    </div>
                    <b>{{ item.value }}</b>
                    <span>{{ item.label }}</span>
                  </div>
                  <div v-if="index < learningLoop.length - 1" class="loop-line">
                    <WebIcon aria-hidden="true" type="arrowright" size="20" color="#AFC8FF" />
                  </div>
                </template>
              </div>
            </div>
            <div class="card distribution-panel">
              <heading title="会话状态分布" />
              <div class="distribution">
                <div class="donut" :style="donutStyle">
                  <div>
                    <b>{{ sessionDistribution.activePercent }}%</b>
                    <span>进行中</span>
                  </div>
                </div>
                <div class="legend">
                  <div>
                    <span class="blue" />
                    <span>进行中</span>
                    <b>{{ sessionDistribution.active }}</b>
                  </div>
                  <div>
                    <span />
                    <span>已完成</span>
                    <b>{{ sessionDistribution.completed }}</b>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="overview-grid lower">
            <div class="card">
              <heading title="最近学生" />
              <div class="table-head">
                <span>学生</span>
                <span>年级</span>
                <span>错题</span>
                <span>会话</span>
              </div>
              <button
                role="button"
                v-for="student in workbench.students.slice(0, 7)"
                :key="student.id"
                class="student-row"
                @click="openStudent(student.id)"
              >
                <div>
                  <span class="avatar">{{ initials(student.name) }}</span>
                  <b>{{ student.name }}</b>
                </div>
                <span>{{ student.grade }}</span>
                <strong>{{ student.question_count }}</strong>
                <strong>{{ student.session_count }}</strong>
              </button>
              <empty-view v-if="!workbench.students.length" text="尚无学生数据" />
            </div>
            <div class="card">
              <heading title="最近教学会话" />
              <button
                role="button"
                v-for="item in workbench.sessions.slice(0, 7)"
                :key="item.id"
                class="session-row"
                @click="openSession(item.id)"
              >
                <div :class="['session-icon', item.status === 'active' ? 'active' : 'done']">
                  <WebIcon
                    aria-hidden="true"
                    type="chat-filled"
                    size="21"
                    :color="item.status === 'active' ? 'var(--color-primary)' : '#168A45'"
                  />
                </div>
                <div>
                  <b><math-text :text="item.question_title" inline /></b>
                  <span>{{ item.student_name }} · {{ stageName(item.stage) }}</span>
                </div>
                <small>{{ clock(item.updated_at) }}</small>
                <WebIcon aria-hidden="true" type="right" size="18" color="#98A2B3" />
              </button>
              <empty-view v-if="!workbench.sessions.length" text="尚无教学会话" />
            </div>
          </div>
        </div>

        <div v-else-if="section === 'students'" class="split">
          <div class="card side-list">
            <heading title="学生列表" :subtitle="`共 ${workbench.students.length} 名学生`" />
            <button
              role="button"
              v-for="student in workbench.students"
              :key="student.id"
              :class="['select-row', { selected: selectedStudentId === student.id }]"
              @click="openStudent(student.id)"
            >
              <span class="avatar">{{ initials(student.name) }}</span>
              <div>
                <b>{{ student.name }}</b>
                <span>{{ student.grade }} · {{ student.question_count }} 道错题</span>
              </div>
              <WebIcon aria-hidden="true" type="right" size="18" color="#98A2B3" />
            </button>
            <empty-view v-if="!workbench.students.length" text="尚无学生数据" />
          </div>
          <div class="detail">
            <div v-if="!studentDetail" class="state compact">
              <WebIcon aria-hidden="true" type="person-filled" size="42" color="#AFC8FF" />
              <b>请选择一名学生</b>
              <span>查看知识掌握、常见误区和复习安排</span>
            </div>
            <template v-else>
              <div class="profile">
                <span>{{ initials(studentDetail.student.name) }}</span>
                <div>
                  <span>学生画像</span>
                  <b>{{ studentDetail.student.name }}</b>
                  <p>
                    {{ studentDetail.student.grade }} ·
                    {{ studentDetail.student.learning_goal || '暂未设置学习目标' }}
                  </p>
                </div>
                <div class="profile-metrics">
                  <div>
                    <b>{{ studentDetail.metrics.questions }}</b>
                    <span>错题</span>
                  </div>
                  <div>
                    <b>{{ studentDetail.metrics.sessions }}</b>
                    <span>会话</span>
                  </div>
                  <div>
                    <b>{{ studentDetail.metrics.pending_reviews }}</b>
                    <span>待复习</span>
                  </div>
                </div>
              </div>
              <div class="detail-grid">
                <div class="card">
                  <heading title="知识掌握" />
                  <div
                    v-for="item in studentDetail.mastery"
                    :key="`${item.subject}-${item.knowledge_point}`"
                    class="progress-row"
                  >
                    <div>
                      <b><math-text :text="item.knowledge_point" inline /></b>
                      <span>{{ item.subject }} · {{ item.evidence_count }} 条证据</span>
                    </div>
                    <strong>{{ percent(item.score) }}</strong>
                    <div class="progress"><div :style="{ width: percent(item.score) }" /></div>
                  </div>
                  <empty-view
                    v-if="!studentDetail.mastery.length"
                    text="完成教学后会形成知识掌握记录"
                  />
                </div>
                <div class="card">
                  <heading title="高频误区" />
                  <div
                    v-for="item in studentDetail.misconceptions"
                    :key="item.code"
                    class="risk-row"
                  >
                    <div class="risk-icon">
                      <WebIcon aria-hidden="true" type="info-filled" size="20" color="#D97706" />
                    </div>
                    <div>
                      <b><math-text :text="item.label" inline /></b>
                      <span>{{ item.evidence_count }} 条学习证据</span>
                      <div class="risk-progress">
                        <div :style="{ width: percent(item.probability) }" />
                      </div>
                    </div>
                    <strong>{{ percent(item.probability) }}</strong>
                  </div>
                  <empty-view
                    v-if="!studentDetail.misconceptions.length"
                    text="目前没有集中出现的误区"
                  />
                </div>
              </div>
              <div class="card">
                <heading title="复习计划" />
                <div class="review-grid">
                  <div v-for="item in studentDetail.reviews" :key="item.id" class="review">
                    <div class="calendar">
                      <WebIcon
                        aria-hidden="true"
                        type="calendar-filled"
                        size="22"
                        color="var(--color-primary)"
                      />
                    </div>
                    <div>
                      <b><math-text :text="item.reason" inline /></b>
                      <span>{{ fullTime(item.due_at) }}</span>
                    </div>
                    <span>{{ reviewStatus(item.status) }}</span>
                  </div>
                </div>
                <empty-view v-if="!studentDetail.reviews.length" text="暂无复习计划" />
              </div>
            </template>
          </div>
        </div>

        <div v-else-if="section === 'sessions'" class="split sessions-split">
          <div class="card side-list">
            <heading title="教学会话" :subtitle="`最近 ${workbench.sessions.length} 条记录`" />
            <button
              role="button"
              v-for="item in workbench.sessions"
              :key="item.id"
              :class="['select-row', { selected: selectedSessionId === item.id }]"
              @click="openSession(item.id)"
            >
              <div :class="['session-icon', item.status === 'active' ? 'active' : 'done']">
                <WebIcon
                  aria-hidden="true"
                  type="chat-filled"
                  size="19"
                  :color="item.status === 'active' ? 'var(--color-primary)' : '#168A45'"
                />
              </div>
              <div>
                <b><math-text :text="item.question_title" inline /></b>
                <span>{{ item.student_name }} · {{ stageName(item.stage) }}</span>
              </div>
              <WebIcon aria-hidden="true" type="right" size="18" color="#98A2B3" />
            </button>
            <empty-view v-if="!workbench.sessions.length" text="尚无教学会话" />
          </div>
          <div class="detail">
            <div v-if="!sessionDetail" class="state compact">
              <WebIcon aria-hidden="true" type="chat-filled" size="42" color="#AFC8FF" />
              <b>请选择一个教学会话</b>
              <span>查看智能体的观察、决策、行动和认知更新</span>
            </div>
            <template v-else>
              <div class="summary-grid">
                <div>
                  <span>当前学生</span>
                  <b>{{ sessionDetail.student?.name || '未知学生' }}</b>
                </div>
                <div>
                  <span>当前题目</span>
                  <b><math-text :text="sessionDetail.question?.title || '未命名题目'" inline /></b>
                </div>
                <div>
                  <span>教学阶段</span>
                  <b>{{ stageName(sessionDetail.session.stage) }}</b>
                </div>
                <div>
                  <span>掌握估计</span>
                  <b class="primary-text">{{ percent(sessionDetail.session.mastery_score) }}</b>
                </div>
              </div>
              <div class="diagnosis">
                <div class="diagnosis-icon">
                  <WebIcon
                    aria-hidden="true"
                    type="search"
                    size="28"
                    color="var(--color-primary)"
                  />
                </div>
                <div>
                  <span>智能体观察到的错因</span>
                  <b>
                    <math-text
                      :text="sessionDetail.diagnosis?.root_misconception || '该会话暂无错因诊断'"
                      inline
                    />
                  </b>
                  <p>
                    <math-text
                      :text="sessionDetail.diagnosis?.first_error_text || '尚未定位具体首错步骤'"
                      inline
                    />
                  </p>
                </div>
                <div class="strategy">
                  <span>采用的教学策略</span>
                  <b>
                    <math-text
                      :text="sessionDetail.diagnosis?.recommended_strategy || '根据对话动态选择'"
                      inline
                    />
                  </b>
                </div>
              </div>
              <div class="trace-grid">
                <div class="card">
                  <heading title="可验证智能体轨迹" />
                  <div
                    v-for="(event, index) in sessionDetail.trace"
                    :key="event.id"
                    class="trace-step"
                  >
                    <div class="axis">
                      <span>{{ index + 1 }}</span>
                      <i />
                    </div>
                    <div class="trace-card">
                      <div class="trace-head">
                        <div>
                          <WebIcon
                            aria-hidden="true"
                            type="paperplane-filled"
                            size="20"
                            color="var(--color-primary)"
                          />
                          <b>{{ event.agent }}</b>
                        </div>
                        <span>{{ clock(event.time) }}</span>
                      </div>
                      <div class="decision">
                        <span>教学决策</span>
                        <b><math-text :text="event.decision" inline /></b>
                        <em
                          v-if="event.verification?.status"
                          :class="['verify-badge', event.verification.status]"
                        >
                          {{ verificationName(event.verification.status) }}
                        </em>
                      </div>
                      <p>
                        <math-text :text="event.goal || '根据当前学习状态推进下一步教学'" inline />
                      </p>
                      <div
                        v-if="event.observation?.memory_summary"
                        class="agent-block memory-block"
                      >
                        <label>长期记忆</label>
                        <math-text :text="event.observation.memory_summary" inline />
                        <small>{{ event.observation.memory_count || 0 }} 条可追溯证据</small>
                      </div>
                      <div v-if="event.plan?.steps?.length" class="agent-block">
                        <label>执行计划</label>
                        <ol>
                          <li v-for="step in event.plan.steps" :key="step">
                            <math-text :text="step" inline />
                          </li>
                        </ol>
                      </div>
                      <div v-for="action in event.actions" :key="action.id" class="tool">
                        <b>{{ action.tool }}</b>
                        <span>{{ compactJson(action.output) }}</span>
                      </div>
                      <div v-if="event.verification?.evidence_refs?.length" class="evidence">
                        <WebIcon
                          aria-hidden="true"
                          type="checkbox-filled"
                          size="17"
                          color="#168A45"
                        />
                        <span>证据：{{ event.verification.evidence_refs.join(' · ') }}</span>
                      </div>
                    </div>
                  </div>
                  <empty-view v-if="!sessionDetail.trace.length" text="该会话尚未记录智能体轨迹" />
                </div>
                <div class="card cognition">
                  <heading title="认知变化" />
                  <div
                    v-for="item in sessionDetail.cognitive_updates"
                    :key="item.id"
                    class="cognition-row"
                  >
                    <div>
                      <b><math-text :text="item.entity_key" inline /></b>
                      <span :class="item.new_value >= item.old_value ? 'up' : 'down'">
                        {{ signedDelta(item) }}
                      </span>
                    </div>
                    <math-text :text="item.reason || '认知状态变化'" inline />
                    <div class="compare-label">
                      <span>学习前 {{ percent(item.old_value) }}</span>
                      <span>学习后 {{ percent(item.new_value) }}</span>
                    </div>
                    <div class="compare">
                      <div class="before" :style="{ width: percent(item.old_value) }" />
                      <div class="after" :style="{ width: percent(item.new_value) }" />
                    </div>
                  </div>
                  <empty-view
                    v-if="!sessionDetail.cognitive_updates.length"
                    text="该会话暂无认知更新"
                  />
                </div>
              </div>
            </template>
          </div>
        </div>

        <div v-else class="system-grid">
          <div v-for="item in systemCards" :key="item.label" class="system-card">
            <div :class="['system-icon', item.tone]">
              <WebIcon aria-hidden="true" :type="item.icon" size="28" :color="item.color" />
            </div>
            <span>{{ item.label }}</span>
            <b>{{ item.value }}</b>
            <span>{{ item.status }}</span>
          </div>
          <div class="card access">
            <div>
              <WebIcon
                aria-hidden="true"
                type="info-filled"
                size="28"
                color="var(--color-primary)"
              />
            </div>
            <div>
              <b>只读访问</b>
              <p>工作台只查询学生学习数据，不修改答案、诊断、教学会话、认知模型或系统配置。</p>
              <span>敏感字段和模型内部推理不会进入工作台响应。</span>
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { browser } from '@/platform/browser.js'
import MathText from '@/components/math-text/math-text.vue'
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
  background: `conic-gradient(var(--color-primary) 0 ${sessionDistribution.value.activePercent * 3.6}deg,#E8EEFC ${sessionDistribution.value.activePercent * 3.6}deg 360deg)`, // taste-skill-ignore: flat chart segments encode actual active/completed session shares.
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
    color: 'var(--color-primary)',
  },
  {
    label: '文本线路',
    value: workbench.value.system.provider.text_entries,
    status: '可用线路',
    icon: 'paperplane-filled',
    tone: 'primary',
    color: 'var(--color-primary)',
  },
  {
    label: '视觉线路',
    value: workbench.value.system.provider.vision_entries,
    status: '可用线路',
    icon: 'image',
    tone: 'primary',
    color: 'var(--color-primary)',
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
      near_transfer: '类似题练习',
      far_transfer: '综合练习',
      teach_back: '理解检查',
      finished: '已完成',
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
    browser.reLaunch({ url: roleHome(store.role) })
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
.brand span {
  display: block;
}
.brand b {
  font-size: 19px;
}
.brand span {
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
.sidebar-foot > span,
.sidebar-foot > b {
  display: block;
}
.sidebar-foot > span {
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
  min-height: 72px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: center;
  justify-content: space-between;
  margin-bottom: 26px;
}
.topbar > div:first-child {
  grid-column: 2;
  grid-row: 1;
  text-align: center;
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
  font-size: 17px;
  font-weight: 500;
  margin-top: 0;
}
.page-desc {
  font-size: 15px;
  color: var(--color-text-secondary);
  margin-top: 5px;
}
.service {
  grid-column: 3;
  grid-row: 1;
  justify-self: end;
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
.service span {
  display: block;
}
.service b {
  font-size: 15px;
}
.service span {
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
.metric-card > span,
.metric-card > b,
.metric-card > small {
  display: block;
}
.metric-card > span {
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
.heading span {
  display: block;
}
.heading b {
  font-size: 19px;
}
.heading span {
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
.loop-step > div {
  width: 54px;
  height: 54px;
  border-radius: 17px;
  background: var(--color-primary-soft);
  display: grid;
  place-items: center;
  margin: 0 auto 9px;
}
.loop-step b,
.loop-step span {
  display: block;
}
.loop-step b {
  font-size: 22px;
}
.loop-step span {
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
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: 28px;
}
.donut {
  flex-shrink: 0;
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
.donut > div {
  position: relative;
  z-index: 1;
  text-align: center;
}
.donut b,
.donut span {
  display: block;
}
.donut b {
  font-size: 27px;
}
.donut span {
  font-size: 13px;
  color: var(--color-text-secondary);
}
.legend > div {
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
.legend span {
  color: var(--color-text-secondary);
  white-space: nowrap;
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
.student-row > div {
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
.session-row span {
  display: block;
}
.session-row b,
.select-row b {
  font-size: 15px;
}
.session-row span,
.session-row small,
.select-row span {
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
.state span {
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
}
.select-row b,
.select-row span {
  display: block;
}
.profile {
  padding: 26px;
  border-radius: 20px;
  background: var(--color-surface);
  color: var(--color-text-primary);
  display: flex;
  align-items: center;
  gap: 18px;
}
.profile > span {
  width: 64px;
  height: 64px;
  border-radius: 20px;
  background: var(--color-surface-subtle);
  display: grid;
  place-items: center;
  font-size: 27px;
  font-weight: 700;
}
.profile > div:nth-child(2) {
  flex: 1;
}
.profile > div > span,
.profile > div > b {
  display: block;
}
.profile > div > b {
  font-size: 25px;
}
.profile p {
  font-size: 14px;
  margin: 5px 0;
}
.profile-metrics {
  display: flex;
}
.profile-metrics > div {
  min-width: 80px;
  padding: 7px 16px;
  text-align: center;
  border-left: 1px solid #ffffff45;
}
.profile-metrics b {
  font-size: 23px;
}
.profile-metrics span {
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
.progress-row span {
  display: block;
}
.progress-row b,
.risk-row b {
  font-size: 15px;
}
.progress-row span,
.risk-row span {
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
.progress > div {
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
.risk-progress > div {
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
.review span {
  display: block;
}
.review b {
  font-size: 14px;
}
.review span {
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
.summary-grid > div {
  padding: 18px 20px;
  border-radius: 17px;
  background: #fff;
  border: 1px solid var(--color-border);
}
.summary-grid span,
.summary-grid b {
  display: block;
}
.summary-grid span {
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
.diagnosis span,
.diagnosis b {
  display: block;
}
.diagnosis span {
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
  padding: 16px;
  border-radius: 12px;
  background: var(--color-primary-soft);
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
.trace-head > div,
.decision,
.cognition-row > div,
.compare-label {
  display: flex;
  align-items: center;
}
.trace-head,
.cognition-row > div,
.compare-label {
  justify-content: space-between;
}
.trace-head > div,
.decision {
  gap: 8px;
}
.trace-head b {
  font-size: 16px;
}
.trace-head > span {
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
.tool span {
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
.agent-block span,
.agent-block small {
  display: block;
}
.agent-block label {
  font-size: 12px;
  color: var(--color-primary);
  font-weight: 650;
}
.agent-block span {
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
.tool span {
  display: block;
}
.tool b {
  font-size: 14px;
}
.tool span {
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
.evidence span {
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
.cognition-row > span {
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
.compare div {
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
.system-card > span,
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
.system-card > span {
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
.access > div:first-child {
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
.access span {
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
  .brand > div:last-child,
  .readonly span,
  .nav-item span,
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
  .brand > div:last-child {
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
  .brand span {
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
  .nav-item span {
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
  .sidebar-foot > span,
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
    font-size: 17px;
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
  .metric-card > span,
  .metric-card > small {
    font-size: 12px;
  }
  .heading {
    padding: 16px;
  }
  .heading b {
    font-size: 17px;
  }
  .heading span {
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
  .loop-step > div {
    width: 40px;
    height: 40px;
    border-radius: 8px;
  }
  .loop-step span {
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
  .student-row > div,
  .session-row > div,
  .select-row > div {
    min-width: 0;
  }
  .student-row > div {
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
  .session-row span,
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
  .access > div:first-child {
    width: 36px;
    height: 36px;
  }
}
</style>
