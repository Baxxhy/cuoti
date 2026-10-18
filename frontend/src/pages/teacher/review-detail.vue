<template>
  <view class="teacher-page">
    <app-header title="人工复核" subtitle="AI 原始证据与人工结论分别保存" back />
    <view class="teacher-content">
      <state-panel
        v-if="loading || error || !data"
        :state="error ? 'error' : 'loading'"
        :message="error"
        @retry="load"
      />
      <template v-else>
        <view class="two-column">
          <view>
            <view class="teacher-card">
              <view class="card-heading">
                <text>题目与学生作答</text>
                <text class="tag">v{{ data.task.version }}</text>
              </view>
              <text class="evidence-text">{{ data.question.question_text }}</text>
              <view class="image-list">
                <image
                  v-for="asset in visibleAssets"
                  :key="asset.id"
                  :src="asset.url"
                  mode="widthFix"
                />
              </view>
              <image
                v-if="data.attempt?.handwriting_image_url"
                class="student-handwriting"
                :src="data.attempt.handwriting_image_url"
                mode="widthFix"
              />
              <view class="field">
                <text class="field-label">学生答案</text>
                <text class="evidence-text">
                  {{ data.attempt?.answer || data.task.ai_result?.student_answer || '无' }}
                </text>
              </view>
              <view class="field">
                <text class="field-label">学生步骤</text>
                <text class="evidence-text">
                  {{ (data.attempt?.steps || []).join('\n') || '无' }}
                </text>
              </view>
            </view>
            <view class="teacher-card">
              <view class="card-heading"><text>标准答案与参考步骤</text></view>
              <text class="evidence-text">
                {{
                  data.teacher_question?.standard_answer ||
                  data.analysis?.final_answer ||
                  '标准答案不完整'
                }}
              </text>
              <view
                v-for="(step, index) in referenceSteps"
                :key="step.id || index"
                class="teacher-row"
              >
                <text class="tag">{{ index + 1 }}</text>
                <text class="evidence-text row-main">{{ step.text || step }}</text>
              </view>
            </view>
          </view>
          <view>
            <view class="teacher-card">
              <view class="card-heading">
                <text>判题证据</text>
                <text class="tag warn">{{ data.task.ai_result?.verdict }}</text>
              </view>
              <text class="evidence-text">
                AI：{{ data.task.ai_result?.feedback || '无说明' }}\n规则：{{
                  data.task.rule_result?.method || '无'
                }}
                /
                {{
                  data.task.rule_result?.correct === true
                    ? '正确'
                    : data.task.rule_result?.correct === false
                      ? '错误'
                      : '不确定'
                }}\n证据：{{ (data.task.ai_result?.evidence || []).join('\n') }}\n冲突：{{
                  data.task.has_conflict ? '是' : '否'
                }}\nOCR：{{
                  data.ocr?.confidence != null
                    ? Math.round(data.ocr.confidence * 100) + '%'
                    : '无记录'
                }}
              </text>
            </view>
            <view class="teacher-card">
              <view class="card-heading"><text>人工结论</text></view>
              <view class="section-tabs">
                <text
                  v-for="option in conclusions"
                  :key="option.value"
                  :class="{ active: form.conclusion === option.value }"
                  @click="form.conclusion = option.value"
                >
                  {{ option.label }}
                </text>
              </view>
              <view class="field">
                <text class="field-label">复核理由（必填）</text>
                <textarea v-model="form.reason" placeholder="简短说明依据" />
              </view>
              <view v-if="form.conclusion === 'partially_correct'" class="field">
                <text class="field-label">得分</text>
                <input v-model="form.score" type="digit" placeholder="0-100" />
              </view>
              <template
                v-if="
                  form.conclusion === 'confirmed_incorrect' ||
                  form.conclusion === 'partially_correct'
                "
              >
                <view class="field">
                  <text class="field-label">第一个关键错误</text>
                  <textarea v-model="form.first_key_error" placeholder="指出最早影响结论的错误" />
                </view>
                <view class="field">
                  <text class="field-label">错误类型</text>
                  <input v-model="form.error_type" placeholder="如：计算错误、概念混淆" />
                </view>
              </template>
              <view class="field">
                <text class="field-label">给学生的提示</text>
                <textarea v-model="form.student_hint" placeholder="一两句话，不直接泄露答案" />
              </view>
              <view class="field">
                <text class="field-label">下一步学习任务</text>
                <input v-model="form.next_task" placeholder="如：复习一次函数斜率" />
              </view>
              <view class="teacher-actions">
                <button class="primary" :disabled="busy" @click="submit">
                  {{ busy ? '提交中…' : '确认结论' }}
                </button>
              </view>
            </view>
          </view>
        </view>
      </template>
    </view>
  </view>
</template>
<script setup>
import { computed, reactive, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { getData, postData } from '@/api/index.js'
import { back } from '@/utils/navigation.js'
const data = ref(null),
  busy = ref(false)
let id = ''
const conclusions = [
  { label: '确认正确', value: 'confirmed_correct' },
  { label: '确认错误', value: 'confirmed_incorrect' },
  { label: '部分正确', value: 'partially_correct' },
  { label: '退回重做', value: 'resubmit' },
  { label: '题目有问题', value: 'question_issue' },
]
const form = reactive({
  conclusion: '',
  score: null,
  reason: '',
  first_key_error: '',
  error_type: '',
  student_hint: '',
  next_task: '',
  allow_learning_update: true,
})
const visibleAssets = computed(() =>
    (data.value?.assets || []).filter((x) =>
      ['original', 'crop', 'student_working_figure'].includes(x.kind),
    ),
  ),
  referenceSteps = computed(() =>
    data.value?.reference_steps?.length
      ? data.value.reference_steps
      : data.value?.teacher_question?.reference_steps || [],
  )
async function loadData() {
  data.value = await getData(`/teachers/reviews/${id}`)
}
async function submit() {
  if (busy.value) return
  if (
    form.conclusion === 'partially_correct' &&
    (form.score === null ||
      form.score === '' ||
      !Number.isFinite(Number(form.score)) ||
      Number(form.score) < 0 ||
      Number(form.score) > 100)
  )
    return uni.showToast({ title: '请填写 0 到 100 的有效分数', icon: 'none' })
  if (!form.conclusion || !form.reason)
    return uni.showToast({ title: '请选择结论并填写理由', icon: 'none' })
  busy.value = true
  try {
    await postData(`/teachers/reviews/${id}/decision`, {
      ...form,
      version: data.value.task.version,
      score:
        form.conclusion === 'partially_correct' && form.score !== '' && form.score !== null
          ? Number(form.score)
          : null,
    })
    uni.showToast({ title: '已保存', icon: 'success' })
    setTimeout(() => back('/pages/teacher/reviews'), 500)
  } catch (err) {
    if (err.statusCode === 409) await load()
  } finally {
    busy.value = false
  }
}
onLoad((q) => {
  id = q.id
  load()
})
const error = ref(''),
  loading = ref(true)
async function load() {
  loading.value = true
  error.value = ''
  try {
    await loadData()
  } catch (err) {
    error.value = err.message || '暂时无法加载，请重试'
  } finally {
    loading.value = false
  }
}
</script>
<style lang="scss">
@import './teacher.scss';
</style>

<style scoped>
.student-handwriting {
  width: 100%;
  margin: 12px 0;
}
</style>
