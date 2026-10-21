<template>
  <view class="page">
    <app-header title="学习" />
    <view class="page-content">
      <view class="learning-heading"><text>错题巩固</text></view>
      <view class="feature-list">
        <button
          tabindex="0"
          role="button"
          v-for="item in learningPrimaryEntries"
          :key="item.url"
          class="feature-link"
          :aria-label="item.title"
          @click="go(item.url)"
          @keydown.enter.prevent="go(item.url)"
          @keydown.space.prevent
          @keyup.space.prevent="go(item.url)"
        >
          <view class="feature-icon">
            <uni-icons
              aria-hidden="true"
              :type="item.icon"
              size="24"
              color="var(--color-primary)"
            />
          </view>
          <view class="feature-copy">
            <text>{{ item.title }}</text>
          </view>
          <uni-icons
            aria-hidden="true"
            class="feature-arrow"
            type="right"
            size="18"
            color="var(--color-text-secondary)"
          />
        </button>
      </view>
      <view class="learning-heading"><text>练习与考试</text></view>
      <view class="learning-gateways">
        <button
          role="button"
          v-for="entry in studyEntries"
          :key="entry.url"
          :class="['learning-gateway', entry.tone]"
          @click="go(entry.url)"
        >
          <uni-icons aria-hidden="true" :type="entry.icon" size="30" color="var(--color-primary)" />
          <text>{{ entry.title }}</text>
          <uni-icons aria-hidden="true" type="right" size="17" color="var(--color-primary)" />
        </button>
      </view>
      <view class="learning-heading"><text>学习分析</text></view>
      <view class="analysis-list">
        <button
          v-for="item in analysisEntries"
          :key="item.url"
          class="analysis-link"
          role="button"
          tabindex="0"
          :aria-label="item.title"
          @click="go(item.url)"
          @keydown.enter.prevent="go(item.url)"
          @keydown.space.prevent
          @keyup.space.prevent="go(item.url)"
        >
          <uni-icons
            class="analysis-icon"
            aria-hidden="true"
            :type="item.icon"
            size="21"
            color="var(--color-primary)"
          />
          <text class="analysis-label">{{ item.title }}</text>
          <uni-icons aria-hidden="true" type="right" size="17" color="var(--color-text-tertiary)" />
        </button>
      </view>
      <view class="records-group">
        <button
          aria-label="学习记录"
          tabindex="0"
          role="button"
          class="record-link"
          :aria-expanded="moreOpen"
          @click="moreOpen = !moreOpen"
          @keydown.enter.prevent="moreOpen = !moreOpen"
          @keydown.space.prevent
          @keyup.space.prevent="moreOpen = !moreOpen"
        >
          <text>学习记录</text>
          <uni-icons
            aria-hidden="true"
            :type="moreOpen ? 'top' : 'bottom'"
            size="18"
            color="var(--color-text-secondary)"
          />
        </button>
        <view v-if="moreOpen" class="feature-list secondary-list">
          <button
            tabindex="0"
            role="button"
            v-for="item in learningRecordEntries"
            :key="item.url"
            class="feature-link"
            @click="go(item.url)"
            @keydown.enter.prevent="go(item.url)"
            @keydown.space.prevent
            @keyup.space.prevent="go(item.url)"
          >
            <text>{{ item.title }}</text>
            <uni-icons
              aria-hidden="true"
              type="right"
              size="18"
              color="var(--color-text-secondary)"
            />
          </button>
        </view>
      </view>
    </view>
    <tab-bar current="learning" />
  </view>
</template>
<script setup>
import { ref } from 'vue'
import {
  studyEntries,
  learningPrimaryEntries,
  learningRecordEntries,
} from '@/constants/learning.js'
import { go } from '@/utils/navigation.js'
const moreOpen = ref(false)
const analysisEntries = [
  { title: '易错地图', icon: 'map', url: '/pages/error-map/error-map' },
  { title: '知识关系', icon: 'link', url: '/pages/analysis/analysis?relations=1' },
  { title: '学习报告', icon: 'bars', url: '/pages/analysis/analysis' },
]
</script>
<style scoped lang="scss">
.learning-heading {
  margin: 8px 0 12px;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-secondary);
}
.feature-list {
  padding: 0 16px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  margin-bottom: 24px;
}
.feature-link {
  display: flex;
  align-items: center;
  width: 100%;
  gap: 12px;
  min-height: 60px;
  padding: 12px 0;
  margin: 0;
  text-align: left;
  background: transparent;
  border-radius: 0;
}
.feature-link + .feature-link {
  border-top: 1px solid var(--color-border);
}
.feature-icon {
  flex: none;
  width: 28px;
  display: flex;
  align-items: center;
}
.feature-copy {
  flex: 1;
  min-width: 0;
  font-size: 16px;
}
.feature-arrow {
  flex: none;
}
.learning-gateways {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 12px;
}
.learning-gateway {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  min-height: 64px;
  margin: 0;
  padding: 14px 12px;
  background: var(--color-surface);
  border: 0;
  border-radius: 12px;
  text-align: left;
  line-height: 1.5;
}
.learning-gateway > text:not(.uni-icons) {
  flex: 1;
  font-size: 15px;
}
.learning-gateway .uni-icons {
  flex: none;
  line-height: 1;
}
.learning-gateway > :last-child {
  display: none;
}
.analysis-list,
.records-group {
  background: var(--color-surface);
  border-radius: 12px;
  padding: 0 16px;
  margin-bottom: 16px;
}
.analysis-link {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  min-height: 54px;
  padding: 12px 0;
  margin: 0;
  background: transparent;
  color: var(--color-text-primary);
  text-align: left;
  border-radius: 0;
}
.analysis-link + .analysis-link {
  border-top: 1px solid var(--color-border);
}
.analysis-label {
  flex: 1;
  font-size: 15px;
}
.analysis-icon {
  width: 24px;
  flex: none;
}
.record-link {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  min-height: 52px;
  margin: 0;
  padding: 12px 0;
  background: transparent;
  color: var(--color-text-secondary);
  border-radius: 0;
  font-size: 14px;
  font-weight: 500;
  text-align: left;
}
.secondary-list {
  margin: 0;
  padding: 0;
  border: 0;
  border-radius: 0;
  border-top: 1px solid var(--color-border);
}
.secondary-list .feature-link {
  justify-content: space-between;
  min-height: 50px;
  font-size: 15px;
  color: var(--color-text-primary);
}
.analysis-link:active,
.secondary-list .feature-link:active {
  background: var(--color-primary-soft);
}
</style>
