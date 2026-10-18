<template>
  <view v-if="data" class="student-report">
    <view class="report-profile">
      <text class="report-eyebrow">学习近况</text>
      <text class="report-name">{{ data.student?.name }}的学习报告</text>
      <text class="report-suggestion">{{ data.suggestion }}</text>
    </view>
    <view class="report-stats">
      <view>
        <b>{{ data.summary?.questions || 0 }}</b>
        <text>错题记录</text>
      </view>
      <view>
        <b>{{ data.summary?.completed_sessions || 0 }}</b>
        <text>完成教学</text>
      </view>
      <view>
        <b>{{ data.summary?.review_records || 0 }}</b>
        <text>复习记录</text>
      </view>
    </view>
    <view class="report-section">
      <view class="report-heading">
        <text>需要巩固的知识</text>
        <small>学习记录估计</small>
      </view>
      <view v-for="item in shownMastery" :key="reportPointKey(item)" class="mastery">
        <view class="mastery-heading">
          <view>
            <text class="subject">{{ item.subject }}</text>
            <math-text :text="item.knowledge_point" inline />
          </view>
          <b>{{ Math.round(item.mastery_score * 100) }}%</b>
        </view>
        <view class="progress"><view :style="{ width: item.mastery_score * 100 + '%' }" /></view>
        <text class="record-note">{{ item.evidence_count || 0 }} 条学习证据</text>
      </view>
      <text v-if="!mastery.length" class="report-empty">还没有知识掌握记录。</text>
      <text v-else class="record-note">这些估计需通过独立作答和复习继续确认。</text>
      <button
        v-if="mastery.length > 3"
        class="report-toggle"
        role="button"
        :aria-expanded="allMastery"
        @click="allMastery = !allMastery"
      >
        {{ allMastery ? '收起知识记录' : `查看全部 ${mastery.length} 项知识` }}
      </button>
    </view>
    <view class="report-section">
      <view class="report-heading"><text>需要留意的错因</text></view>
      <view
        v-for="item in shownCauses"
        :key="JSON.stringify([item.subject, item.label])"
        class="cause-row"
      >
        <text class="subject">{{ item.subject }}</text>
        <math-text :text="item.label" inline />
      </view>
      <text v-if="!causes.length" class="report-empty">
        暂无明确的待处理错因，完成错因核对后会更新。
      </text>
      <button
        v-if="causes.length > 3"
        class="report-toggle"
        role="button"
        :aria-expanded="allCauses"
        @click="allCauses = !allCauses"
      >
        {{ allCauses ? '收起错因记录' : `查看全部 ${causes.length} 项错因` }}
      </button>
      <button
        v-if="otherCauses.length"
        class="report-toggle"
        role="button"
        :aria-expanded="showOther"
        @click="showOther = !showOther"
      >
        {{ showOther ? '收起其他记录' : `已解决与待核对记录（${otherCauses.length}）` }}
      </button>
      <template v-if="showOther">
        <view v-for="item in otherCauses" :key="item.id" class="cause-row">
          <text class="subject">
            {{ item.subject }} · {{ item.status === 'resolved' ? '已解决记录' : '分类待核对' }}
          </text>
          <math-text
            :text="reportCauseLabel(item.label || item.code) || '尚未明确具体错因'"
            inline
          />
        </view>
      </template>
    </view>
  </view>
</template>
<script setup>
import { computed, ref, watch } from 'vue'
import { reportCauses, reportCauseLabel, reportMastery, reportPointKey } from '@/utils/report.js'
const props = defineProps({ data: Object })
const allMastery = ref(false),
  allCauses = ref(false),
  showOther = ref(false)
const mastery = computed(() =>
  reportMastery(props.data?.mastery || []).sort((a, b) => a.mastery_score - b.mastery_score),
)
const causes = computed(() => reportCauses(props.data?.misconceptions || []))
const otherCauses = computed(() =>
  (props.data?.misconceptions || []).filter(
    (item) => item.status === 'resolved' || !reportCauseLabel(item.label || item.code),
  ),
)
const shownMastery = computed(() => (allMastery.value ? mastery.value : mastery.value.slice(0, 3)))
const shownCauses = computed(() => (allCauses.value ? causes.value : causes.value.slice(0, 3)))
watch(
  () => props.data,
  () => {
    allMastery.value = false
    allCauses.value = false
    showOther.value = false
  },
)
</script>
<style scoped lang="scss">
.report-profile {
  padding: 30rpx;
  border-radius: 24rpx;
  background: var(--color-primary-soft);
  border: 1rpx solid var(--color-border);
}
.report-eyebrow,
.report-name,
.report-suggestion {
  display: block;
}
.report-eyebrow {
  color: var(--color-primary);
  font-size: 24rpx;
  font-weight: 600;
}
.report-name {
  font-size: 36rpx;
  line-height: 1.5;
  font-weight: 650;
  margin-top: 10rpx;
}
.report-suggestion {
  color: var(--color-text-secondary);
  font-size: 28rpx;
  line-height: 1.7;
  margin-top: 14rpx;
}
.report-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  margin: 28rpx 0;
}
.report-stats > view {
  text-align: center;
  border-right: 1rpx solid var(--color-border);
}
.report-stats > view:last-child {
  border-right: 0;
}
.report-stats b,
.report-stats text {
  display: block;
}
.report-stats b {
  font-size: 34rpx;
}
.report-stats text {
  font-size: 24rpx;
  color: var(--color-text-secondary);
  margin-top: 6rpx;
}
.report-section {
  padding: 28rpx;
  margin-bottom: 24rpx;
  background: var(--color-surface);
  border: 1rpx solid var(--color-border);
  border-radius: 24rpx;
}
.report-heading {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12rpx;
  justify-content: space-between;
  margin-bottom: 18rpx;
  font-weight: 600;
  font-size: 30rpx;
}
.report-heading small {
  font-size: 23rpx;
  font-weight: 400;
  color: var(--color-text-secondary);
}
.mastery {
  margin: 24rpx 0;
}
.mastery-heading {
  display: flex;
  gap: 18rpx;
  align-items: center;
  justify-content: space-between;
  font-size: 29rpx;
}
.mastery-heading > view {
  min-width: 0;
  flex: 1;
}
.mastery-heading b {
  flex-shrink: 0;
  color: var(--color-primary);
}
.subject {
  display: block;
  font-size: 23rpx;
  color: var(--color-text-secondary);
  margin-bottom: 6rpx;
}
.record-note,
.report-empty {
  display: block;
  color: var(--color-text-secondary);
  font-size: 24rpx;
  line-height: 1.7;
}
.record-note {
  margin-top: 8rpx;
}
.progress {
  margin-top: 12rpx;
  height: 8rpx;
  border-radius: 8rpx;
  background: var(--color-border);
  overflow: hidden;
}
.progress > view {
  height: 100%;
  background: var(--color-primary);
}
.cause-row {
  padding: 18rpx 0;
  font-size: 29rpx;
  line-height: 1.6;
  border-bottom: 1rpx solid var(--color-border);
}
.cause-row:last-child {
  border-bottom: 0;
}
.report-toggle {
  width: 100%;
  min-height: 88rpx;
  padding: 18rpx 0;
  margin-top: 12rpx;
  text-align: left;
  border-radius: 0;
  font-size: 28rpx;
  background: transparent;
  color: var(--color-primary);
}
</style>
