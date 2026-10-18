<template>
  <view class="page library-page">
    <app-header
      title="知识卡片"
      subtitle="查清概念，再回到题目中运用"
      back
      back-fallback="/pages/learning/learning"
    />
    <view class="page-content">
      <view v-if="!code" class="library-search">
        <view class="search-row">
          <input
            v-model="query"
            placeholder="搜索概念、公式或易错点"
            aria-label="搜索知识"
            confirm-type="search"
            @confirm="search"
          />
          <button class="small-btn" @click="search">搜索</button>
        </view>
        <view class="library-filters">
          <picker :range="['全部学科', ...subjects]" @change="changeSubject">
            <view class="filter-button">{{ subject || '全部学科' }} ▾</view>
          </picker>
          <picker :range="gradeOptions" @change="changeGrade">
            <view class="filter-button">{{ grade || '全部年级' }} ▾</view>
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
        <h2>{{ card.name }}</h2>
        <math-text :text="card.content?.definition || '这张知识卡暂未补充定义。'" />
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
        <view v-for="section in relationSections" :key="section.key" class="knowledge-section">
          <template v-if="card[section.key]?.length">
            <h3>{{ section.title }}</h3>
            <button
              v-for="related in card[section.key]"
              :key="related.code"
              class="card-link"
              @click="openCard(related.code)"
            >
              {{ related.name }}
              <text>查看</text>
            </button>
          </template>
        </view>
        <button
          class="primary-btn"
          @click="go(scopedQuestionURL({ subject: card.subject, search: card.name }))"
        >
          查看相关错题
        </button>
        <button class="secondary-btn" @click="go('/pages/library/library', { replace: true })">
          返回知识检索
        </button>
        <text class="boundary-note">读懂知识后，再通过独立作答检验掌握。</text>
      </template>
      <template v-else>
        <text class="card-meta">
          本次显示 {{ cards.length }} 张知识卡，最多50张，可缩小条件检索。
        </text>
        <button
          v-for="item in cards"
          :key="item.code"
          class="knowledge-result"
          @click="openCard(item.code)"
        >
          <text>{{ item.name }}</text>
          <small>
            {{ item.subject }} · {{ item.content?.grade || '通用' }} ·
            {{ item.content?.chapter || '知识卡' }}
          </small>
        </button>
        <view v-if="!cards.length" class="empty">
          <text>没有找到符合条件的知识卡</text>
          <button class="small-btn" @click="resetSearch">清除条件</button>
        </view>
      </template>
    </view>
  </view>
</template>
<script setup>
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { getData } from '@/api/index.js'
import { CORE_SUBJECTS as subjects, MIDDLE_SCHOOL_GRADES } from '@/constants/education.js'
import { go } from '@/utils/navigation.js'
import { scopedQuestionURL } from '@/utils/learning.js'
const query = ref(''),
  subject = ref(''),
  grade = ref(''),
  code = ref(''),
  cards = ref([]),
  card = ref(null),
  loading = ref(true),
  error = ref('')
const gradeOptions = ['全部年级', '初中', '高中', ...MIDDLE_SCHOOL_GRADES]
const relationSections = [
  { key: 'prerequisites', title: '先补这些知识' },
  { key: 'next_knowledge', title: '接下来可了解' },
]
let requestId = 0
async function search() {
  const current = ++requestId
  loading.value = true
  error.value = ''
  try {
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
  go(`/pages/library/library?code=${encodeURIComponent(value)}`)
}
function changeSubject(event) {
  subject.value = subjects[Number(event.detail.value) - 1] || ''
  search()
}
function changeGrade(event) {
  grade.value = Number(event.detail.value) ? gradeOptions[Number(event.detail.value)] : ''
  search()
}
function resetSearch() {
  query.value = ''
  subject.value = ''
  grade.value = ''
  search()
}
onLoad((q) => {
  code.value = q.code || ''
  query.value = q.q || ''
  subject.value = q.subject || ''
  grade.value = gradeOptions.includes(q.grade) && q.grade !== '全部年级' ? q.grade : ''
  if (code.value) loadCard()
  else search()
})
</script>
<style scoped lang="scss">
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
  padding: 18px 0;
  background: transparent;
  border-radius: 0;
  border-bottom: 1px solid var(--color-border);
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
  justify-content: space-between;
  min-height: 48px;
  padding: 12px;
  margin: 8px 0;
  background: white;
  font-size: 15px;
}
.card-link text {
  color: var(--color-primary);
}
</style>
