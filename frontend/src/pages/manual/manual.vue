<template>
  <view class="page manual-page">
    <app-header title="手动录入" back />
    <view class="page-content">
      <view class="form-section">
        <text class="intro">填写完整题目和原来的作答。含图形的题目建议拍照录入。</text>
        <view class="metadata">
          <view class="field">
            <text class="field-label">学科</text>
            <picker :range="subjects" @change="subject = subjects[Number($event.detail.value)]">
              <view class="picker-value">
                {{ subject }}
                <uni-icons type="bottom" size="16" color="var(--color-text-tertiary)" />
              </view>
            </picker>
          </view>
          <view class="field">
            <text class="field-label">年级</text>
            <input v-model="grade" class="input" maxlength="30" placeholder="例如：初二" />
          </view>
        </view>
        <view class="field">
          <text class="field-label">题型</text>
          <picker
            :range="questionTypes"
            @change="questionType = questionTypes[Number($event.detail.value)]"
          >
            <view class="picker-value">
              {{ questionType }}
              <uni-icons type="bottom" size="16" color="var(--color-text-tertiary)" />
            </view>
          </picker>
        </view>
        <view class="field">
          <text class="field-label">
            完整题目
            <text class="required">*</text>
          </text>
          <textarea
            v-model="questionText"
            class="textarea"
            maxlength="12000"
            auto-height
            placeholder="请输入完整题干，支持数学公式。"
          />
        </view>
        <view v-if="isChoice" class="field">
          <text class="field-label">
            选项
            <text class="required">*</text>
          </text>
          <text class="muted help">填写 2–8 个选项。</text>
          <view v-for="(_, index) in options" :key="index" class="option-editor">
            <text>{{ optionLabel(index) }}</text>
            <textarea
              v-model="options[index]"
              class="textarea"
              auto-height
              maxlength="3000"
              :placeholder="`填写选项 ${optionLabel(index)}`"
            />
            <button
              v-if="options.length > 2"
              class="option-remove"
              @click="options.splice(index, 1)"
            >
              删除
            </button>
          </view>
          <button v-if="options.length < 8" class="secondary-btn" @click="options.push('')">
            添加选项
          </button>
        </view>
        <view class="field">
          <text class="field-label">我当时的答案</text>
          <textarea
            v-model="studentAnswer"
            class="textarea"
            maxlength="6000"
            auto-height
            placeholder="填写原来的答案，没有作答可留空"
          />
        </view>
        <view class="field">
          <text class="field-label">我的解题步骤（选填）</text>
          <text class="muted help">每行一步，保留原来的解题思路，最多 30 步。</text>
          <textarea
            v-model="stepsText"
            class="textarea"
            maxlength="12000"
            auto-height
            placeholder="每行输入一个解题步骤"
          />
        </view>
        <text v-if="error" class="error-text" role="alert">{{ error }}</text>
        <button class="primary-btn" :disabled="busy || !questionText.trim()" @click="save">
          {{ busy ? '正在保存…' : '保存并查看错题' }}
        </button>
        <text class="muted help">保存后可开始错因诊断。补充解题步骤，有助于定位错误。</text>
      </view>
    </view>
  </view>
</template>

<script setup>
import { computed, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { getData, postData } from '@/api/index.js'
import { CORE_SUBJECTS as subjects } from '@/constants/education.js'
const subject = ref('数学'),
  grade = ref(''),
  questionText = ref(''),
  studentAnswer = ref(''),
  stepsText = ref(''),
  busy = ref(false),
  error = ref('')
const questionTypes = ['综合题', '单选题', '多选题'],
  questionType = ref('综合题'),
  options = ref(['', ''])
const isChoice = computed(() => questionType.value !== '综合题')
const optionLabel = (index) => String.fromCharCode(65 + index)
async function save() {
  if (busy.value || !questionText.value.trim()) return
  const steps = stepsText.value
    .split('\n')
    .map((value) => value.trim())
    .filter(Boolean)
  if (steps.length > 30) {
    error.value = '解题步骤最多 30 步，请合并后再保存。'
    return
  }
  if (isChoice.value && options.value.some((value) => !value.trim())) {
    error.value = '请填写每个选项，或删除多余的空选项。'
    return
  }
  busy.value = true
  error.value = ''
  try {
    const item = await postData('/questions/manual', {
      question_text: questionText.value.trim(),
      question_type: questionType.value,
      options: isChoice.value
        ? options.value.map((text, index) => ({ label: optionLabel(index), text: text.trim() }))
        : [],
      student_answer: studentAnswer.value.trim(),
      student_steps: steps,
      subject: subject.value,
      grade: grade.value.trim() || null,
    })
    uni.redirectTo({ url: `/pages/detail/detail?id=${item.id}` })
  } catch (err) {
    error.value = err.message || '保存失败，内容仍在，请重试。'
  } finally {
    busy.value = false
  }
}
onLoad(async () => {
  try {
    const profile = await getData('/dashboard', { silent: true })
    if (!grade.value) grade.value = profile.grade || profile.profile?.grade || ''
  } catch {}
})
</script>

<style scoped lang="scss">
.manual-page {
  padding-bottom: 20px;
}
.form-section {
  padding: 0 0 12px;
}
.intro {
  display: block;
  padding-bottom: 12px;
  border-bottom: 0.5px solid var(--color-border);
  color: var(--color-text-secondary);
  font-size: 13px;
  line-height: 1.75;
}
.metadata {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.field {
  margin-top: 14px;
}
.field-label {
  display: block;
  margin-bottom: 6px;
  color: var(--color-text-primary);
  font-size: 13px;
  font-weight: 500;
}
.picker-value {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 43px;
  box-sizing: border-box;
  padding: 9px 10px;
  border: 0.5px solid var(--color-border);
  border-radius: 4px;
  background: #fff;
  font-size: 14px;
}
.input {
  width: 100%;
  height: 43px;
  min-height: 43px;
  box-sizing: border-box;
  padding: 9px 10px;
  border: 0.5px solid var(--color-border);
  border-radius: 4px;
  background: #fff;
  color: var(--color-text-primary);
  font-size: 14px;
}
.textarea {
  width: 100%;
  min-height: 70px;
  box-sizing: border-box;
  padding: 10px;
  border: 0.5px solid var(--color-border);
  border-radius: 4px;
  background: #fff;
  font-size: 14px;
  line-height: 1.75;
}
.required,
.error-text {
  color: var(--color-error);
}
.help {
  display: block;
  margin: 5px 0;
  color: var(--color-text-secondary);
  font-size: 12px;
  line-height: 1.7;
}
.option-editor {
  display: flex;
  align-items: flex-start;
  gap: 7px;
  margin: 8px 0;
}
.option-editor > text {
  padding-top: 10px;
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-secondary);
}
.option-editor .textarea {
  flex: 1;
  min-width: 0;
  min-height: 43px;
}
.option-remove {
  flex: none;
  min-height: 36px;
  margin: 0;
  padding: 6px;
  background: transparent;
  color: var(--color-text-secondary);
  font-size: 12px;
}
.option-remove::after {
  border: 0;
}
.error-text {
  display: block;
  margin-top: 8px;
  font-size: 12px;
}
.primary-btn {
  margin-top: 16px;
}
</style>
