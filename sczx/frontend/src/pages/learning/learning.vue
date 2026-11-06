<template>
  <div class="page">
    <app-header title="学习" />
    <div class="page-content">
      <div class="learning-heading"><span>错题巩固</span></div>
      <div class="feature-list">
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
          <div class="feature-icon">
            <WebIcon
              aria-hidden="true"
              :type="item.icon"
              size="24"
              color="var(--color-primary)"
            />
          </div>
          <div class="feature-copy">
            <span>{{ item.title }}</span>
          </div>
          <WebIcon
            aria-hidden="true"
            class="feature-arrow"
            type="right"
            size="18"
            color="var(--color-text-secondary)"
          />
        </button>
      </div>
      <div class="learning-heading"><span>练习与考试</span></div>
      <div class="learning-gateways">
        <button
          role="button"
          v-for="entry in studyEntries"
          :key="entry.url"
          :class="['learning-gateway', entry.tone]"
          @click="go(entry.url)"
        >
          <WebIcon aria-hidden="true" :type="entry.icon" size="30" color="var(--color-primary)" />
          <span>{{ entry.title }}</span>
          <WebIcon aria-hidden="true" type="right" size="17" color="var(--color-primary)" />
        </button>
      </div>
      <div class="learning-heading"><span>学习分析</span></div>
      <div class="analysis-list">
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
          <WebIcon
            class="analysis-icon"
            aria-hidden="true"
            :type="item.icon"
            size="21"
            color="var(--color-primary)"
          />
          <span class="analysis-label">{{ item.title }}</span>
          <WebIcon aria-hidden="true" type="right" size="17" color="var(--color-text-tertiary)" />
        </button>
      </div>
      <div class="learning-heading"><span>学习记录</span></div>
      <div class="record-shortcuts">
        <button
          v-for="(item, index) in learningRecordEntries"
          :key="item.url"
          role="button"
          tabindex="0"
          class="record-shortcut"
          :aria-label="item.title"
          @click="go(item.url)"
          @keydown.enter.prevent="go(item.url)"
          @keydown.space.prevent
          @keyup.space.prevent="go(item.url)"
        >
          <WebIcon
            aria-hidden="true"
            :type="['compose', 'calendar', 'star'][index]"
            size="23"
            color="var(--color-text-secondary)"
          />
          <span>{{ item.title }}</span>
        </button>
      </div>
    </div>
    <tab-bar current="learning" />
  </div>
</template>
<script setup>
import {
  studyEntries,
  learningPrimaryEntries,
  learningRecordEntries,
} from '@/constants/learning.js'
import { go } from '@/utils/navigation.js'
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
.learning-gateway > span:not(.uni-icons) {
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
.analysis-list {
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
.record-shortcuts {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  padding: 8px 0;
  background: var(--color-surface);
  border-radius: 12px;
}
.record-shortcut {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  min-width: 0;
  min-height: 80px;
  margin: 0;
  padding: 12px 4px;
  background: transparent;
  color: var(--color-text-primary);
  font-size: 13px;
  line-height: 1.4;
  border-radius: 8px;
}
.analysis-link:active,
.record-shortcut:active {
  background: var(--color-primary-soft);
}
</style>
