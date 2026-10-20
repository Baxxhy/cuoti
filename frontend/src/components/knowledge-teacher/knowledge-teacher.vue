<template>
  <view class="knowledge-teacher">
    <button role="button" class="teacher-toggle" :aria-expanded="opened" @click="toggle">
      <text>AI 老师讲解</text>
      <uni-icons :type="opened ? 'top' : 'bottom'" size="16" aria-hidden="true" />
    </button>
    <view v-if="opened" class="teacher-content">
      <text v-if="loading" role="status">正在读取讲解记录…</text>
      <view v-if="latest" class="lesson">
        <text v-if="latest.source_current === false" class="lesson-notice">
          知识卡已更新，可以重新提问查看新版讲解。
        </text>
        <text class="lesson-question">{{ latest.prompt || '讲解这个知识点' }}</text>
        <math-text :text="latest.result.explanation" />
        <view class="lesson-points">
          <math-text
            v-for="(point, index) in latest.result.key_points"
            :key="index"
            :text="point"
          />
        </view>
        <view class="lesson-check">
          <text>想一想</text>
          <math-text :text="latest.result.check_question" />
        </view>
        <text class="lesson-origin">
          AI 讲解 · 参考 {{ latest.result.sources.map((item) => item.name).join('、') }}
        </text>
      </view>
      <textarea
        v-model="prompt"
        :disabled="busy"
        aria-label="想问 AI 老师的问题"
        placeholder="哪里没看懂？也可以直接请求讲解"
        maxlength="400"
        auto-height
      />
      <button role="button" class="primary-btn" :disabled="busy || loading" @click="ask">
        {{ busy ? '老师正在整理讲解…' : prompt.trim() ? '发送问题' : '讲解这个知识点' }}
      </button>
      <text v-if="error" role="alert" class="lesson-error">{{ error }}</text>
      <button
        v-if="lessons.length > 1"
        role="button"
        class="lesson-history-toggle"
        :aria-expanded="showHistory"
        @click="showHistory = !showHistory"
      >
        {{ showHistory ? '收起记录' : '以前的讲解' }}
      </button>
      <view v-if="showHistory" class="lesson-history">
        <button v-for="item in lessons" :key="item.id" role="button" @click="select(item)">
          {{ item.prompt || '讲解这个知识点' }}
        </button>
      </view>
    </view>
  </view>
</template>
<script setup>
import { ref, onBeforeUnmount, watch } from 'vue'
import { getData, postData } from '@/api/index.js'
const props = defineProps({ code: { type: String, required: true } })
const opened = ref(false),
  loading = ref(false),
  busy = ref(false),
  error = ref(''),
  prompt = ref(''),
  lessons = ref([]),
  latest = ref(null),
  showHistory = ref(false)
let revision = 0,
  pending = null
const owner = () => uni.getStorageSync('minddimension_access_token')
const current = (stamp, token) => stamp === revision && token === owner()
async function toggle() {
  opened.value = !opened.value
  if (!opened.value || loading.value || busy.value || lessons.value.length) return
  const stamp = ++revision,
    token = owner()
  loading.value = true
  error.value = ''
  try {
    const result = await getData(`/knowledge/cards/${encodeURIComponent(props.code)}/lessons`)
    if (!current(stamp, token)) return
    lessons.value = result
    latest.value = result[0] || null
  } catch (err) {
    if (current(stamp, token)) error.value = err.message || '讲解记录暂时无法读取'
  } finally {
    if (stamp === revision) loading.value = false
  }
}
async function ask() {
  if (busy.value || loading.value) return
  const stamp = ++revision,
    token = owner(),
    text = prompt.value.trim(),
    code = props.code
  if (!pending || pending.prompt !== text || pending.code !== code)
    pending = {
      code,
      prompt: text,
      request_id: `knowledge-${Date.now()}-${Math.random().toString(36).slice(2)}`,
    }
  const submission = pending
  busy.value = true
  error.value = ''
  try {
    const item = await postData(`/knowledge/cards/${encodeURIComponent(code)}/lessons`, {
      prompt: text,
      request_id: submission.request_id,
    })
    if (!current(stamp, token)) return
    latest.value = item
    lessons.value = [item, ...lessons.value.filter((row) => row.id !== item.id)].slice(0, 10)
    prompt.value = ''
    pending = null
  } catch (err) {
    if (current(stamp, token)) {
      // A source conflict cannot replay the old request; the next explicit
      // submission starts a new one while keeping the student's question.
      if (err.statusCode === 409) pending = null
      error.value = err.message || '讲解暂时没有完成，问题已保留，请重试'
    }
  } finally {
    if (stamp === revision) busy.value = false
  }
}
function select(item) {
  latest.value = item
  showHistory.value = false
}
watch(
  () => props.code,
  () => {
    revision++
    opened.value = false
    lessons.value = []
    latest.value = null
    busy.value = loading.value = false
    pending = null
    prompt.value = ''
    error.value = ''
  },
)
onBeforeUnmount(() => {
  revision++
})
</script>
<style scoped lang="scss">
.knowledge-teacher {
  margin: 20px 0;
  border-top: 1px solid var(--color-border);
  border-bottom: 1px solid var(--color-border);
}
.teacher-toggle {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  margin: 0;
  min-height: 52px;
  padding: 12px 0;
  background: transparent;
  text-align: left;
  font-size: 16px;
}
.teacher-content {
  padding-bottom: 16px;
}
.teacher-content textarea {
  width: 100%;
  min-height: 90px;
  margin: 16px 0 12px;
  padding: 12px;
  font-size: 15px;
  line-height: 1.6;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 10px;
}
.lesson-question {
  display: block;
  margin: 4px 0 12px;
  font-size: 14px;
  font-weight: 600;
}
.lesson {
  font-size: 15px;
  line-height: 1.7;
}
.lesson-points {
  margin: 14px 0;
}
.lesson-check {
  margin: 16px 0;
  padding: 14px;
  background: var(--color-surface);
  border-radius: 10px;
}
.lesson-check > text {
  display: block;
  font-size: 13px;
  margin-bottom: 6px;
  color: var(--color-text-secondary);
}
.lesson-origin,
.lesson-notice {
  display: block;
  font-size: 12px;
  line-height: 1.6;
  color: var(--color-text-secondary);
}
.lesson-error {
  display: block;
  margin: 12px 0;
  font-size: 14px;
  color: var(--color-error);
}
.lesson-history-toggle,
.lesson-history button {
  width: 100%;
  text-align: left;
  margin: 0;
  padding: 12px 0;
  min-height: 44px;
  font-size: 14px;
  background: transparent;
  color: var(--color-text-secondary);
}
</style>
