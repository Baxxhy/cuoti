<template>
  <view class="page preferences-page">
    <app-header title="学习方向" back />
    <view class="page-content">
      <view class="editorial-heading">
        <text class="eyebrow">你的选择，随时可改</text>
        <text class="editorial-title">今天，先照顾眼前的目标。</text>
        <text class="editorial-description">
          选择当前学科和节奏。它们用于组织入口，不代表能力测评。
        </text>
      </view>
      <state-panel
        v-if="loading || error"
        :state="error ? 'error' : 'loading'"
        :message="error"
        @retry="load"
      />
      <form v-else class="learning-settings" @submit.prevent="save">
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
          <text class="field-label">今天想做什么</text>
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
        <view class="preference-field">
          <text class="field-label">建议学习节奏</text>
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
          <text class="evidence-caption">这是你选择的节奏，可以提前结束，不据此判断学习表现。</text>
        </view>
        <text v-if="saveError" class="account-notice" role="alert">{{ saveError }}</text>
        <text v-if="saved" class="saved-preferences" role="status">
          已保存。返回今日后，会按新的学科组织学习入口。
        </text>
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
          {{ saving ? '正在保存…' : '保存学习方向' }}
        </button>
        <button
          aria-label="返回今日"
          role="button"
          tabindex="0"
          class="disclosure-link"
          @keydown.enter.prevent="go('/pages/index/index', { replace: true })"
          @keydown.space.prevent
          @keyup.space.prevent="go('/pages/index/index', { replace: true })"
          @click="go('/pages/index/index', { replace: true })"
        >
          返回今日
          <uni-icons aria-hidden="true" type="right" size="18" />
        </button>
      </form>
    </view>
  </view>
</template>
<script setup>
import { ref } from 'vue'
import { onShow, onHide, onUnload } from '@dcloudio/uni-app'
import { getData, patchData } from '@/api/index.js'
import { go } from '@/utils/navigation.js'
import { CORE_SUBJECTS as subjects } from '@/constants/education.js'
const form = ref({ subject: '', minutes: 10, goal: 'understand', version: 0 }),
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
    if (version === revision) form.value = value
  } catch (err) {
    if (version === revision) error.value = err.message || '学习方向暂时无法读取'
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
    const { subject, minutes, goal, version: sourceVersion } = form.value
    const value = await patchData('/student-preferences', {
      subject,
      minutes,
      goal,
      version: sourceVersion,
    })
    if (version === revision) {
      form.value = value
      saved.value = true
    }
  } catch (err) {
    if (version === revision)
      saveError.value =
        err.statusCode === 409
          ? '另一页面已修改学习方向。请返回再进入，核对最新设置；当前选择仍保留。'
          : err.message || '保存失败，请重试'
  } finally {
    if (version === revision) saving.value = false
  }
}
function clear() {
  revision++
  form.value = { subject: '', minutes: 10, goal: 'understand', version: 0 }
  saving.value = false
  saved.value = false
}
onShow(load)
onHide(clear)
onUnload(clear)
</script>
<style scoped lang="scss">
.learning-settings {
  margin-top: 32px;
  max-width: 560px;
}
.preference-field {
  margin-bottom: 28px;
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
  border-radius: 8px;
  background: var(--color-surface);
  color: var(--color-text-primary);
  font-size: 16px;
}
.preference-options {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}
.preference-options button {
  margin: 0;
  padding: 12px;
  min-height: 48px;
  border: 1px solid var(--color-border);
  background: var(--color-surface);
  color: var(--color-text-primary);
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
</style>
