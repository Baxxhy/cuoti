<template>
  <div class="page framework-page">
    <app-header title="知识框架" back back-fallback="/pages/learning/learning" />
    <div class="page-content">
      <div class="framework-search">
        <WebIcon type="search" size="20" aria-hidden="true" />
        <WebInput
          v-model="query"
          aria-label="搜索知识框架"
          placeholder="搜索知识点或章节"
          maxlength="100"
        />
      </div>
      <div class="framework-filters">
        <WebPicker
          :range="['全部学科', ...subjects]"
          @change="subject = subjects[Number($event.detail.value) - 1] || ''"
        >
          <div class="filter-label">
            {{ subject || '全部学科' }}
            <WebIcon type="bottom" size="14" aria-hidden="true" />
          </div>
        </WebPicker>
        <WebPicker
          :range="gradeOptions"
          @change="
            grade =
              gradeOptions[Number($event.detail.value)] === '全部年级'
                ? ''
                : gradeOptions[Number($event.detail.value)]
          "
        >
          <div class="filter-label">
            {{ grade || '全部年级' }}
            <WebIcon type="bottom" size="14" aria-hidden="true" />
          </div>
        </WebPicker>
        <button
          role="button"
          class="weak-filter"
          :class="{ selected: weakOnly }"
          :aria-pressed="weakOnly"
          @click="weakOnly = !weakOnly"
        >
          需要巩固
        </button>
      </div>
      <state-panel
        v-if="loading || error"
        :state="error ? 'error' : 'loading'"
        :message="error"
        @retry="load"
      />
      <template v-else>
        <div v-for="group in visibleGroups" :key="group.key" class="chapter">
          <button
            role="button"
            class="chapter-heading"
            :class="{ 'direct-knowledge': direct(group) }"
            :aria-expanded="direct(group) ? undefined : !!opened[group.key]"
            @click="direct(group) ? open(group.nodes[0]) : (opened[group.key] = !opened[group.key])"
          >
            <div>
              <small>{{ group.subject }} · {{ group.grade || '通用' }}</small>
              <span>{{ group.chapter }}</span>
              <small v-if="direct(group)">
                {{ knowledgeProgress(group.nodes[0]) }}
                <template v-if="group.nodes[0].question_count">
                  · {{ group.nodes[0].question_count }} 道相关错题
                </template>
              </small>
            </div>
            <span v-if="!direct(group)" class="chapter-count">{{ group.nodes.length }}</span>
            <WebIcon
              :type="direct(group) ? 'right' : opened[group.key] ? 'top' : 'bottom'"
              size="16"
              aria-hidden="true"
            />
          </button>
          <div v-if="opened[group.key] && !direct(group)" class="chapter-nodes">
            <button
              v-for="node in group.nodes"
              :key="node.code"
              role="button"
              class="knowledge-node"
              @click="open(node)"
            >
              <div>
                <math-text :text="node.name" inline />
                <small>
                  {{ knowledgeProgress(node) }}
                  <template v-if="node.question_count">
                    · {{ node.question_count }} 道相关错题
                  </template>
                </small>
              </div>
              <WebIcon type="right" size="16" aria-hidden="true" />
            </button>
          </div>
        </div>
        <button
          v-if="groups.length > visibleCount"
          role="button"
          class="secondary-btn"
          @click="visibleCount += 12"
        >
          查看更多章节
        </button>
        <div v-if="!groups.length" class="framework-empty">
          <span>
            {{ weakOnly ? '当前条件下没有需要巩固的知识记录' : '没有找到符合条件的知识' }}
          </span>
          <button role="button" class="secondary-btn" @click="reset">清除条件</button>
        </div>
      </template>
    </div>
  </div>
</template>
<script setup>
import { browser } from '@/platform/browser.js'
import { computed, ref, watch } from 'vue'
import { onLoad, onShow, onHide, onUnload } from '@/platform/lifecycle.js'
import { getData } from '@/api/index.js'
import { go } from '@/utils/navigation.js'
import { CORE_SUBJECTS as subjects, MIDDLE_SCHOOL_GRADES } from '@/constants/education.js'
import { frameworkGroups, knowledgeProgress } from '@/utils/knowledge-framework.js'
const nodes = ref([]),
  subject = ref(''),
  grade = ref(''),
  query = ref(''),
  weakOnly = ref(false),
  opened = ref({}),
  loading = ref(true),
  error = ref('')
const gradeOptions = ['全部年级', ...MIDDLE_SCHOOL_GRADES]
const groups = computed(() =>
  frameworkGroups(nodes.value, {
    subject: subject.value,
    grade: grade.value,
    query: query.value,
    weakOnly: weakOnly.value,
  }),
)
const questionId = ref('')
const visibleCount = ref(12)
const visibleGroups = computed(() => groups.value.slice(0, visibleCount.value))
const direct = (group) => group.nodes.length === 1 && group.nodes[0].name === group.chapter
watch([subject, grade, query, weakOnly], () => {
  visibleCount.value = 12
})
let defaultsLoaded = false,
  subjectSpecified = false,
  gradeSpecified = false
let revision = 0,
  active = false
async function load() {
  const stamp = ++revision,
    token = browser.getStorageSync('minddimension_access_token')
  loading.value = true
  error.value = ''
  try {
    const data = await getData('/knowledge/framework')
    if (!active || stamp !== revision || token !== browser.getStorageSync('minddimension_access_token'))
      return
    nodes.value = data.nodes
    if (!defaultsLoaded) {
      if (!subjectSpecified) subject.value = data.default_subject || ''
      if (!gradeSpecified && gradeOptions.includes(data.default_grade))
        grade.value = data.default_grade
      defaultsLoaded = true
    }
    if (!Object.keys(opened.value).length && groups.value[0])
      opened.value[groups.value[0].key] = true
  } catch (err) {
    if (active && stamp === revision) error.value = err.message || '知识框架暂时无法读取'
  } finally {
    if (active && stamp === revision) loading.value = false
  }
}
function open(node) {
  go(
    `/pages/library/library?code=${encodeURIComponent(node.code)}${questionId.value ? `&question=${encodeURIComponent(questionId.value)}` : ''}`,
  )
}
function reset() {
  subject.value = grade.value = query.value = ''
  weakOnly.value = false
}
onLoad((params) => {
  questionId.value = params.question || ''
  subjectSpecified = 'subject' in params
  gradeSpecified = 'grade' in params
  subject.value = params.subject || ''
  grade.value = gradeOptions.includes(params.grade) ? params.grade : ''
})
onShow(() => {
  active = true
  load()
})
function leave() {
  active = false
  revision++
  nodes.value = []
}
onHide(leave)
onUnload(leave)
</script>
<style scoped lang="scss">
.framework-search {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 14px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 12px;
}
.framework-search .web-input {
  flex: 1;
  min-width: 0;
  min-height: 44px;
  font-size: 15px;
}
.framework-filters {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin: 14px 0;
}
.filter-label,
.weak-filter {
  padding: 10px;
  min-height: 44px;
  border-radius: 8px;
  font-size: 13px;
  background: var(--color-surface);
}
.weak-filter {
  display: flex;
  align-items: flex-start;
  justify-content: center;
  margin: 0;
  color: var(--color-text-secondary);
}
.weak-filter.selected {
  color: var(--color-primary);
  background: var(--color-primary-soft);
}
.framework-note {
  display: block;
  margin: 16px 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--color-text-secondary);
}
.chapter {
  margin-bottom: 10px;
  background: var(--color-surface);
  border-radius: 12px;
  overflow: hidden;
}
.chapter-heading {
  display: flex;
  gap: 12px;
  width: 100%;
  align-items: center;
  padding: 14px;
  margin: 0;
  text-align: left;
  background: transparent;
}
.chapter-heading > div {
  flex: 1;
  min-width: 0;
}
.chapter-heading small,
.knowledge-node small {
  display: block;
  margin: 3px 0;
  font-size: 12px;
  color: var(--color-text-secondary);
  line-height: 1.5;
}
.chapter-heading span {
  font-size: 15px;
  overflow-wrap: anywhere;
}
.chapter-count {
  flex-shrink: 0;
  color: var(--color-text-secondary);
}
.chapter-nodes {
  padding: 0 14px;
}
.knowledge-node {
  display: flex;
  width: 100%;
  align-items: center;
  gap: 12px;
  padding: 12px 0;
  min-height: 60px;
  border-top: 1px solid var(--color-border);
  background: transparent;
  border-radius: 0;
  text-align: left;
}
.knowledge-node > div {
  flex: 1;
  min-width: 0;
  font-size: 15px;
}
.framework-empty {
  padding: 28px 0;
  font-size: 14px;
  text-align: center;
}
.framework-empty button {
  margin-top: 18px;
}
</style>
