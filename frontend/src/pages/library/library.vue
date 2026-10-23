<template>
  <view class="page library-page">
    <app-header title="知识卡片" back back-fallback="/pages/learning/learning" />
    <view class="page-content">
      <view v-if="!code" class="library-search">
        <button role="button" class="framework-entry" @click="openFramework">
          按章节查看知识框架
          <uni-icons type="right" size="16" aria-hidden="true" />
        </button>
        <view class="search-row">
          <input
            v-model="query"
            placeholder="搜索概念、公式或易错点"
            aria-label="搜索知识"
            confirm-type="search"
            @confirm="search"
          />
          <button role="button" class="small-btn" @click="search">搜索</button>
        </view>
        <view class="library-filters">
          <picker :range="['全部学科', ...subjects]" @change="changeSubject">
            <view class="filter-button">
              {{ subject || '全部学科' }}
              <uni-icons aria-hidden="true" type="bottom" size="14" />
            </view>
          </picker>
          <picker :range="gradeOptions" @change="changeGrade">
            <view class="filter-button">
              {{ grade || '全部年级' }}
              <uni-icons aria-hidden="true" type="bottom" size="14" />
            </view>
          </picker>
        </view>
      </view>
      <state-panel
        v-if="loading || error"
        :state="error ? 'error' : 'loading'"
        :message="error"
        @retry="code ? loadCard() : search()"
      />
      <template v-else-if="card">
        <text class="card-meta">{{ card.subject }} · {{ card.content?.grade || '通用' }}</text>
        <text v-if="card.content?.grade_note" class="card-meta">{{ card.content.grade_note }}</text>
        <h2><math-text :text="card.name" inline /></h2>
        <math-text
          v-if="hasUsefulDefinition(card.content?.definition)"
          :text="card.content.definition"
        />
        <view v-if="card.content?.formulas?.length" class="knowledge-section">
          <h3>关键公式</h3>
          <math-text v-for="(formula, i) in card.content.formulas" :key="i" :text="formula" />
        </view>
        <view v-if="card.content?.common_misconceptions?.length" class="knowledge-section">
          <h3>容易混淆</h3>
          <math-text
            v-for="(value, i) in card.content.common_misconceptions"
            :key="i"
            :text="value"
          />
        </view>
        <view v-if="card.content?.worked_example" class="knowledge-section">
          <h3>理解示例</h3>
          <math-text :text="card.content.worked_example" />
        </view>
        <knowledge-teacher :key="card.code" :code="card.code" />
        <view v-for="section in relationSections" :key="section.key" class="knowledge-section">
          <template v-if="card[section.key]?.length">
            <h3>{{ section.title }}</h3>
            <button
              role="button"
              v-for="related in card[section.key]"
              :key="related.code"
              class="card-link"
              :aria-label="'查看' + related.name"
              @click="openCard(related.code)"
            >
              <math-text :text="related.name" inline />
              <uni-icons type="right" size="16" aria-hidden="true" />
            </button>
          </template>
        </view>
        <button
          v-if="questionId"
          role="button"
          class="primary-btn"
          :disabled="explaining"
          @click="explainWithQuestion"
        >
          {{ explaining ? '正在打开讲解…' : '结合原题讲解' }}
        </button>
        <text v-if="explainError" class="explain-error" role="alert">{{ explainError }}</text>
        <button
          role="button"
          class="secondary-btn"
          @click="go(scopedQuestionURL({ subject: card.subject, search: card.name }))"
        >
          查看相关错题
        </button>
        <button
          role="button"
          class="secondary-btn"
          @click="go('/pages/library/library', { replace: true })"
        >
          返回知识检索
        </button>
      </template>
      <template v-else>
        <text class="card-meta">{{ cards.length }} 张知识卡</text>
        <button
          role="button"
          v-for="item in cards"
          :key="item.code"
          class="knowledge-result"
          @click="openCard(item.code)"
        >
          <math-text :text="item.name" inline />
          <small>
            <math-text
              :text="
                [
                  item.subject,
                  item.content?.grade || '通用',
                  item.content?.chapter !== item.name ? item.content?.chapter : '',
                ]
                  .filter(Boolean)
                  .join(' · ')
              "
              inline
            />
          </small>
        </button>
        <view v-if="!cards.length" class="empty">
          <text>没有找到符合条件的知识卡</text>
          <button role="button" class="small-btn" @click="resetSearch">清除条件</button>
        </view>
      </template>
    </view>
  </view>
</template>
<script setup>
import MathText from '@/components/math-text/math-text.vue'
import KnowledgeTeacher from '@/components/knowledge-teacher/knowledge-teacher.vue'
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { getData, postData } from '@/api/index.js'
import { CORE_SUBJECTS as subjects, MIDDLE_SCHOOL_GRADES } from '@/constants/education.js'
import { go } from '@/utils/navigation.js'
import { scopedQuestionURL } from '@/utils/learning.js'
import { hasUsefulDefinition } from '@/utils/knowledge-content.js'
const query = ref(''),
  subject = ref(''),
  grade = ref(''),
  code = ref(''),
  cards = ref([]),
  card = ref(null),
  loading = ref(true),
  error = ref('')
const questionId = ref(''),
  explaining = ref(false),
  explainError = ref('')
const gradeOptions = ['全部年级', ...MIDDLE_SCHOOL_GRADES]
const relationSections = [
  { key: 'prerequisites', title: '先补这些知识' },
  { key: 'next_knowledge', title: '接下来可了解' },
]
let requestId = 0
let gradeInitialized = false
async function search() {
  const current = ++requestId
  loading.value = true
  error.value = ''
  try {
    if (!gradeInitialized) {
      const preferences = await getData('/student-preferences')
      if (current !== requestId) return
      grade.value = gradeOptions.includes(preferences.grade) ? preferences.grade : ''
      gradeInitialized = true
    }
    const result = await getData(
      `/knowledge/cards?q=${encodeURIComponent(query.value)}&subject=${encodeURIComponent(subject.value)}&grade=${encodeURIComponent(grade.value)}`,
    )
    if (current === requestId) cards.value = result
  } catch (err) {
    if (current === requestId) error.value = err.message || '知识卡暂时无法加载'
  } finally {
    if (current === requestId) loading.value = false
  }
}
async function loadCard() {
  loading.value = true
  error.value = ''
  try {
    card.value = await getData(`/knowledge/cards/${encodeURIComponent(code.value)}`)
  } catch (err) {
    error.value = err.message || '知识卡暂时无法加载'
  } finally {
    loading.value = false
  }
}
function openCard(value) {
  go(
    `/pages/library/library?code=${encodeURIComponent(value)}${questionId.value ? `&question=${encodeURIComponent(questionId.value)}` : ''}`,
  )
}
function openFramework() {
  go(
    `/pages/framework/framework${questionId.value ? `?question=${encodeURIComponent(questionId.value)}&subject=${encodeURIComponent(subject.value)}` : ''}`,
  )
}
async function explainWithQuestion() {
  if (explaining.value || !questionId.value || !card.value) return
  explaining.value = true
  explainError.value = ''
  try {
    const session = await postData('/tutor/sessions', { question_id: questionId.value })
    go(
      `/pages/tutor/tutor?id=${encodeURIComponent(session.id)}&ask=${encodeURIComponent(`请结合这道题讲解“${card.value.name}”，先解释概念，再说明这道题中怎样用。`)}`,
    )
  } catch (err) {
    explainError.value = err.message || '讲解暂时无法打开，请稍后重试'
  } finally {
    explaining.value = false
  }
}
function changeSubject(event) {
  subject.value = subjects[Number(event.detail.value) - 1] || ''
  search()
}
function changeGrade(event) {
  gradeInitialized = true
  grade.value = Number(event.detail.value) ? gradeOptions[Number(event.detail.value)] : ''
  search()
}
function resetSearch() {
  gradeInitialized = true
  query.value = ''
  subject.value = ''
  grade.value = ''
  search()
}
onLoad((q) => {
  questionId.value = q.question || ''
  code.value = q.code || ''
  query.value = q.q || ''
  subject.value = q.subject || ''
  grade.value = gradeOptions.includes(q.grade) && q.grade !== '全部年级' ? q.grade : ''
  gradeInitialized = Boolean(q.grade)
  if (code.value) loadCard()
  else search()
})
</script>
<style scoped lang="scss">
.framework-entry {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  margin: 0 0 12px;
  padding: 10px 0;
  min-height: 44px;
  text-align: left;
  background: transparent;
  font-size: 14px;
  color: var(--color-text-secondary);
}
.explain-error {
  display: block;
  margin: 12px 0;
  color: var(--color-error);
  font-size: 14px;
}
.search-row {
  display: flex;
  gap: 8px;
  align-items: center;
}
.search-row input {
  flex: 1;
  min-width: 0;
  min-height: 48px;
  background: white;
  padding: 10px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
}
.library-filters {
  display: flex;
  gap: 10px;
  margin: 12px 0;
}
.filter-button {
  min-height: 44px;
  padding: 10px;
  background: white;
  border-radius: 8px;
}
.card-meta,
.boundary-note {
  display: block;
  font-size: 13px;
  line-height: 1.6;
  color: var(--color-text-secondary);
  margin: 12px 0;
}
h2 {
  font-size: 22px;
  margin: 16px 0;
}
h3 {
  font-size: 17px;
  margin: 16px 0 10px;
}
.knowledge-result {
  display: block;
  width: 100%;
  text-align: left;
  padding: 16px 20px;
  margin: 12px 0;
  background: var(--color-surface);
  border-radius: 12px;
  border: 0;
}
.knowledge-result text {
  display: block;
  font-size: 17px;
}
.knowledge-result small {
  display: block;
  font-size: 13px;
  margin-top: 6px;
  color: var(--color-text-secondary);
}
.knowledge-section :deep(.math-text) {
  display: block;
  margin: 10px 0;
}
.card-link {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 48px;
  padding: 12px;
  margin: 8px 0;
  background: white;
  font-size: 15px;
}
.card-link :deep(.math-text) {
  flex: 1;
  width: auto;
  margin: 0;
  text-align: left;
}
</style>
