<template>
  <view class="page framework-page">
    <app-header title="知识框架" back back-fallback="/pages/learning/learning" />
    <view class="page-content">
      <view class="framework-search">
        <uni-icons type="search" size="20" aria-hidden="true" />
        <input
          v-model="query"
          aria-label="搜索知识框架"
          placeholder="搜索知识点或章节"
          maxlength="100"
        />
      </view>
      <view class="framework-filters">
        <picker
          :range="['全部学科', ...subjects]"
          @change="subject = subjects[Number($event.detail.value) - 1] || ''"
        >
          <view class="filter-label">
            {{ subject || '全部学科' }}
            <uni-icons type="bottom" size="14" aria-hidden="true" />
          </view>
        </picker>
        <picker
          :range="gradeOptions"
          @change="
            grade =
              gradeOptions[Number($event.detail.value)] === '全部年级'
                ? ''
                : gradeOptions[Number($event.detail.value)]
          "
        >
          <view class="filter-label">
            {{ grade || '全部年级' }}
            <uni-icons type="bottom" size="14" aria-hidden="true" />
          </view>
        </picker>
        <button
          role="button"
          class="weak-filter"
          :class="{ selected: weakOnly }"
          :aria-pressed="weakOnly"
          @click="weakOnly = !weakOnly"
        >
          需要巩固
        </button>
      </view>
      <state-panel
        v-if="loading || error"
        :state="error ? 'error' : 'loading'"
        :message="error"
        @retry="load"
      />
      <template v-else>
        <view v-for="group in visibleGroups" :key="group.key" class="chapter">
          <button
            role="button"
            class="chapter-heading"
            :class="{ 'direct-knowledge': direct(group) }"
            :aria-expanded="direct(group) ? undefined : !!opened[group.key]"
            @click="direct(group) ? open(group.nodes[0]) : (opened[group.key] = !opened[group.key])"
          >
            <view>
              <small>{{ group.subject }} · {{ group.grade || '通用' }}</small>
              <text>{{ group.chapter }}</text>
              <small v-if="direct(group)">
                {{ knowledgeProgress(group.nodes[0]) }}
                <template v-if="group.nodes[0].question_count">
                  · {{ group.nodes[0].question_count }} 道相关错题
                </template>
              </small>
            </view>
            <text v-if="!direct(group)" class="chapter-count">{{ group.nodes.length }}</text>
            <uni-icons
              :type="direct(group) ? 'right' : opened[group.key] ? 'top' : 'bottom'"
              size="16"
              aria-hidden="true"
            />
          </button>
          <view v-if="opened[group.key] && !direct(group)" class="chapter-nodes">
            <button
              v-for="node in group.nodes"
              :key="node.code"
              role="button"
              class="knowledge-node"
              @click="open(node)"
            >
              <view>
                <math-text :text="node.name" inline />
                <small>
                  {{ knowledgeProgress(node) }}
                  <template v-if="node.question_count">
                    · {{ node.question_count }} 道相关错题
                  </template>
                </small>
              </view>
              <uni-icons type="right" size="16" aria-hidden="true" />
            </button>
          </view>
        </view>
        <button
          v-if="groups.length > visibleCount"
          role="button"
          class="secondary-btn"
          @click="visibleCount += 12"
        >
          查看更多章节
        </button>
        <view v-if="!groups.length" class="framework-empty">
          <text>
            {{ weakOnly ? '当前条件下没有需要巩固的知识记录' : '没有找到符合条件的知识' }}
          </text>
          <button role="button" class="secondary-btn" @click="reset">清除条件</button>
        </view>
      </template>
    </view>
  </view>
</template>
<script setup>
import { computed, ref, watch } from 'vue'
import { onLoad, onShow, onHide, onUnload } from '@dcloudio/uni-app'
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
    token = uni.getStorageSync('minddimension_access_token')
  loading.value = true
  error.value = ''
  try {
    const data = await getData('/knowledge/framework')
    if (!active || stamp !== revision || token !== uni.getStorageSync('minddimension_access_token'))
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
.framework-search input {
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
.chapter-heading > view {
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
.chapter-heading text {
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
.knowledge-node > view {
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
