<template>
  <view class="page preferences-page">
    <app-header title="学习设置" back />
    <view class="page-content">
      <state-panel
        v-if="loading || error"
        :state="error ? 'error' : 'loading'"
        :message="error"
        @retry="load"
      />
      <form v-else class="learning-settings" @submit.prevent="save">
        <view class="preference-field">
          <!-- #ifdef H5 -->
          <component :is="'label'" for="current-grade" class="field-label">当前年级</component>
          <component
            :is="'select'"
            id="current-grade"
            class="preference-select"
            :disabled="saving"
            :value="form.grade"
            @change="changeChoice('grade', $event.target.value)"
          >
            <component
              :is="'option'"
              v-if="!grades.includes(form.grade)"
              :value="form.grade"
              disabled
            >
              {{ form.grade || '请选择年级' }}
            </component>
            <component :is="'option'" v-for="grade in grades" :key="grade" :value="grade">
              {{ grade }}
            </component>
          </component>
          <!-- #endif -->
          <!-- #ifndef H5 -->
          <text class="field-label">当前年级</text>
          <picker
            :range="grades"
            :disabled="saving"
            @change="changeChoice('grade', grades[$event.detail.value])"
          >
            <view class="preference-select">{{ form.grade || '请选择年级' }}</view>
          </picker>
          <!-- #endif -->
          <text v-if="form.grade !== loadedGrade" class="grade-note">原有错题和学习记录会保留</text>
        </view>
        <view class="preference-field">
          <!-- #ifdef H5 -->
          <component :is="'label'" for="focus-subject" class="field-label">当前学科</component>
          <component
            :is="'select'"
            id="focus-subject"
            class="preference-select"
            :disabled="saving"
            :value="form.subject"
            @change="changeChoice('subject', $event.target.value)"
          >
            <component :is="'option'" value="" disabled>请选择学科</component>
            <component :is="'option'" v-for="subject in subjects" :key="subject" :value="subject">
              {{ subject }}
            </component>
          </component>
          <!-- #endif -->
          <!-- #ifndef H5 -->
          <text class="field-label">当前学科</text>
          <picker
            :range="subjects"
            @change="changeChoice('subject', subjects[$event.detail.value])"
          >
            <view class="preference-select">{{ form.subject || '请选择学科' }}</view>
          </picker>
          <!-- #endif -->
        </view>
        <view class="preference-field">
          <text class="field-label">优先学习内容</text>
          <view class="preference-options">
            <button
              role="button"
              tabindex="0"
              v-for="goal in goals"
              :key="goal.value"
              :disabled="saving"
              :aria-pressed="form.goal === goal.value"
              :class="{ selected: form.goal === goal.value }"
              @keydown.enter.prevent="changeChoice('goal', goal.value)"
              @keydown.space.prevent
              @keyup.space.prevent="changeChoice('goal', goal.value)"
              @click="changeChoice('goal', goal.value)"
            >
              {{ goal.label }}
            </button>
          </view>
        </view>
        <view v-if="form.goal === 'practice'" class="preference-field">
          <text class="field-label">预计学习时间</text>
          <view class="preference-options">
            <button
              role="button"
              tabindex="0"
              v-for="minutes in [5, 10, 20]"
              :key="minutes"
              :disabled="saving"
              :aria-pressed="form.minutes === minutes"
              :class="{ selected: form.minutes === minutes }"
              @keydown.enter.prevent="changeChoice('minutes', minutes)"
              @keydown.space.prevent
              @keyup.space.prevent="changeChoice('minutes', minutes)"
              @click="changeChoice('minutes', minutes)"
            >
              {{ minutes }} 分钟
            </button>
          </view>
        </view>
        <text v-if="saveError" class="account-notice" role="alert">{{ saveError }}</text>
        <text v-if="saved" class="saved-preferences" role="status">已保存</text>
        <button
          role="button"
          tabindex="0"
          class="primary-btn"
          :disabled="saving || !form.subject"
          @keydown.enter.prevent="save"
          @keydown.space.prevent
          @keyup.space.prevent="save"
          @click="save"
        >
          {{ saving ? '正在保存…' : '保存设置' }}
        </button>
      </form>
    </view>
  </view>
</template>
<script setup>
import { ref } from 'vue'
import { onShow, onHide, onUnload } from '@dcloudio/uni-app'
import { getData, patchData } from '@/api/index.js'
import { CORE_SUBJECTS as subjects, MIDDLE_SCHOOL_GRADES as grades } from '@/constants/education.js'
const form = ref({ grade: '', subject: '', minutes: 10, goal: 'understand', version: 0 }),
  loadedGrade = ref(''),
  loading = ref(true),
  error = ref(''),
  saveError = ref(''),
  saving = ref(false),
  saved = ref(false)
let revision = 0
const goals = [
  { value: 'understand', label: '弄懂一道题' },
  { value: 'practice', label: '巩固一类题' },
  { value: 'review', label: '复习学过的内容' },
]
async function load() {
  const version = ++revision
  loading.value = true
  error.value = ''
  saveError.value = ''
  saved.value = false
  try {
    const value = await getData('/student-preferences')
    if (version === revision) {
      form.value = value
      loadedGrade.value = value.grade
    }
  } catch (err) {
    if (version === revision) error.value = err.message || '学习设置暂时无法读取'
  } finally {
    if (version === revision) loading.value = false
  }
}
function changeChoice(key, value) {
  if (saving.value) return
  form.value[key] = value
  saved.value = false
  saveError.value = ''
}
async function save() {
  if (saving.value || !form.value.subject) return
  const version = revision
  saving.value = true
  saved.value = false
  saveError.value = ''
  try {
    const { grade, subject, minutes, goal, version: sourceVersion } = form.value
    const value = await patchData('/student-preferences', {
      ...(grades.includes(grade) ? { grade } : {}),
      subject,
      minutes,
      goal,
      version: sourceVersion,
    })
    if (version === revision) {
      form.value = value
      loadedGrade.value = value.grade
      saved.value = true
    }
  } catch (err) {
    if (version === revision)
      saveError.value =
        err.statusCode === 409
          ? '另一页面已修改学习设置。请返回再进入，核对最新设置；当前选择仍保留。'
          : err.message || '保存失败，请重试'
  } finally {
    if (version === revision) saving.value = false
  }
}
function clear() {
  revision++
  form.value = { grade: '', subject: '', minutes: 10, goal: 'understand', version: 0 }
  loadedGrade.value = ''
  saving.value = false
  saved.value = false
}
onShow(load)
onHide(clear)
onUnload(clear)
</script>
<style scoped lang="scss">
.learning-settings {
  margin-top: 8px;
  display: block;
  width: 100%;
  max-width: none;
}
.preference-field {
  margin-bottom: 28px;
}
.grade-note {
  display: block;
  margin-top: 8px;
  color: var(--color-text-secondary);
  font-size: 13px;
}
.field-label {
  display: block;
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 12px;
}
.preference-select {
  display: block;
  width: 100%;
  min-height: 48px;
  padding: 12px;
  border: 1px solid var(--color-border);
  border-radius: 12px;
  background: var(--color-surface);
  color: var(--color-text-primary);
  font-size: 16px;
}
.preference-options {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 0;
}
.preference-options button {
  margin: 0;
  padding: 12px;
  min-height: 48px;
  border: 1px solid var(--color-border);
  background: var(--color-bg);
  color: var(--color-text-primary);
  border-radius: 12px;
  font-size: 14px;
}
.preference-options button.selected {
  color: var(--color-primary);
  border-color: var(--color-primary);
  background: var(--color-primary-soft);
}
.saved-preferences {
  display: block;
  margin-bottom: 16px;
  color: var(--color-success);
  font-size: 14px;
}
.preferences-page {
  max-width: 760px;
}
</style>
