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
      <view class="learning-featured">
        <button
          aria-label="易错地图"
          role="button"
          tabindex="0"
          class="disclosure-link"
          @keydown.enter.prevent="go('/pages/error-map/error-map')"
          @keydown.space.prevent
          @keyup.space.prevent="go('/pages/error-map/error-map')"
          @click="go('/pages/error-map/error-map')"
        >
          <uni-icons aria-hidden="true" type="map" size="22" color="var(--color-primary)" />
          <view class="feature-copy">
            <text>易错地图</text>
          </view>
          <uni-icons aria-hidden="true" type="right" size="20" />
        </button>
      </view>
      <button
        role="button"
        tabindex="0"
        class="record-link"
        @click="go('/pages/analysis/analysis?relations=1')"
        @keydown.enter.prevent="go('/pages/analysis/analysis?relations=1')"
        @keydown.space.prevent
        @keyup.space.prevent="go('/pages/analysis/analysis?relations=1')"
      >
        <text>知识关系</text>
        <uni-icons aria-hidden="true" type="right" size="18" color="var(--color-text-secondary)" />
      </button>
      <button
        aria-label="学习报告"
        tabindex="0"
        role="button"
        class="record-link"
        @click="go('/pages/analysis/analysis')"
        @keydown.enter.prevent="go('/pages/analysis/analysis')"
        @keydown.space.prevent
        @keyup.space.prevent="go('/pages/analysis/analysis')"
      >
        <text>学习报告</text>
        <uni-icons aria-hidden="true" type="right" size="18" color="var(--color-text-secondary)" />
      </button>
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
.learning-featured {
  margin-bottom: 12px;
}
.learning-featured .disclosure-link {
  gap: 12px;
}
.record-link {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  min-height: 56px;
  margin: 0;
  padding: 12px 0;
  background: transparent;
  border-radius: 0;
  border-bottom: 1px solid var(--color-border);
  font-size: 15px;
  text-align: left;
}
.secondary-list {
  margin-top: 12px;
}
.secondary-list .feature-link {
  justify-content: space-between;
  font-size: 15px;
}
</style>
