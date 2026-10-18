<template>
  <view class="teacher-page">
    <app-header title="新增题目" subtitle="发布前校对题干、答案和步骤" back />
    <view class="teacher-content">
      <view class="teacher-card">
        <view class="two-column">
          <view>
            <view class="field">
              <text class="field-label">标题</text>
              <input v-model="form.title" />
            </view>
            <view class="field">
              <text class="field-label">学科</text>
              <input v-model="form.subject" />
            </view>
            <view class="field">
              <text class="field-label">年级</text>
              <input v-model="form.grade" />
            </view>
            <view class="field">
              <text class="field-label">题型</text>
              <input v-model="form.question_type" />
            </view>
            <view class="field">
              <text class="field-label">难度</text>
              <input v-model="form.difficulty" />
            </view>
            <view class="field">
              <text class="field-label">知识点（逗号分隔）</text>
              <input v-model="knowledgeText" />
            </view>
          </view>
          <view>
            <view class="field">
              <text class="field-label">题干（必填）</text>
              <textarea v-model="form.question_text" />
            </view>
            <view class="field">
              <text class="field-label">标准答案</text>
              <textarea v-model="form.standard_answer" />
            </view>
            <view class="field">
              <text class="field-label">参考步骤（每行一步）</text>
              <textarea v-model="stepsText" />
            </view>
            <view class="field">
              <text class="field-label">评分点（每行一项）</text>
              <textarea v-model="scoringText" />
            </view>
          </view>
        </view>
        <view class="section-tabs">
          <text
            :class="{ active: form.allow_auto_grade }"
            @click="form.allow_auto_grade = !form.allow_auto_grade"
          >
            {{ form.allow_auto_grade ? '允许自动判题' : '禁止自动判题' }}
          </text>
          <text
            :class="{ active: form.require_handwriting }"
            @click="form.require_handwriting = !form.require_handwriting"
          >
            {{ form.require_handwriting ? '必须手写' : '手写可选' }}
          </text>
        </view>
        <view class="teacher-actions">
          <button class="primary" :disabled="busy" @click="save">
            {{ busy ? '保存中…' : '发布题目' }}
          </button>
        </view>
      </view>
    </view>
  </view>
</template>
<script setup>
import { reactive, ref } from 'vue'
import { postData } from '@/api/index.js'
const busy = ref(false),
  knowledgeText = ref(''),
  stepsText = ref(''),
  scoringText = ref('')
const form = reactive({
  title: '',
  subject: '数学',
  grade: '初二',
  question_type: '综合题',
  difficulty: '中等',
  question_text: '',
  standard_answer: '',
  allow_auto_grade: true,
  require_handwriting: false,
  source_type: 'manual',
})
const lines = (v) =>
  v
    .split(/\n/)
    .map((x) => x.trim())
    .filter(Boolean)
const keywords = (v) =>
  v
    .split(/[\n，,]/)
    .map((x) => x.trim())
    .filter(Boolean)
async function save() {
  if (busy.value) return
  if (!form.question_text.trim()) return uni.showToast({ title: '请填写题干', icon: 'none' })
  busy.value = true
  try {
    await postData('/teachers/questions', {
      ...form,
      knowledge_points: keywords(knowledgeText.value),
      reference_steps: lines(stepsText.value),
      scoring_points: lines(scoringText.value),
      reason: '教师手动录入题目',
    })
    uni.showToast({ title: '已发布', icon: 'success' })
    setTimeout(() => uni.navigateBack(), 500)
  } finally {
    busy.value = false
  }
}
</script>
<style lang="scss">
@import './teacher.scss';
</style>
