<template>
  <view class="page">
    <app-header title="学习" />
    <view class="page-content">
      <view class="learning-heading"><text>练习与考试</text></view>
      <view class="learning-gateways">
        <button
          v-for="entry in studyEntries"
          :key="entry.url"
          :class="['learning-gateway', entry.tone]"
          @click="go(entry.url)"
        >
          <uni-icons
            :type="entry.icon"
            size="30"
            :color="entry.tone === 'orange' ? '#a65916' : '#176cbb'"
          />
          <text>{{ entry.title }}</text>
          <uni-icons
            type="right"
            size="17"
            :color="entry.tone === 'orange' ? '#a65916' : '#176cbb'"
          />
        </button>
      </view>
      <view class="learning-heading"><text>错题与巩固</text></view>
      <view class="learning-featured">
        <button
          aria-label="个人易错地图"
          role="button"
          tabindex="0"
          class="disclosure-link"
          @keydown.enter.prevent="go('/pages/error-map/error-map')"
          @keydown.space.prevent
          @keyup.space.prevent="go('/pages/error-map/error-map')"
          @click="go('/pages/error-map/error-map')"
        >
          <uni-icons type="map" size="22" color="var(--color-primary)" />
          <view class="feature-copy">
            <text>个人易错地图</text>
          </view>
          <uni-icons type="right" size="20" />
        </button>
      </view>
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
            <uni-icons :type="item.icon" size="24" color="var(--color-primary)" />
          </view>
          <view class="feature-copy">
            <text>{{ item.title }}</text>
          </view>
          <uni-icons
            class="feature-arrow"
            type="right"
            size="18"
            color="var(--color-text-secondary)"
          />
        </button>
      </view>
      <button
        aria-label="学习回顾"
        tabindex="0"
        role="button"
        class="record-link"
        @click="go('/pages/analysis/analysis')"
        @keydown.enter.prevent="go('/pages/analysis/analysis')"
        @keydown.space.prevent
        @keyup.space.prevent="go('/pages/analysis/analysis')"
      >
        <text>学习回顾</text>
        <uni-icons type="right" size="18" color="var(--color-text-secondary)" />
      </button>
      <button
        aria-label="更多记录与任务"
        tabindex="0"
        role="button"
        class="record-link"
        :aria-expanded="moreOpen"
        @click="moreOpen = !moreOpen"
        @keydown.enter.prevent="moreOpen = !moreOpen"
        @keydown.space.prevent
        @keyup.space.prevent="moreOpen = !moreOpen"
      >
        <text>更多记录与任务</text>
        <uni-icons
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
          <uni-icons type="right" size="18" color="var(--color-text-secondary)" />
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
.learning-featured {
  margin-bottom: 24px;
  background: var(--color-surface);
  border-radius: 20px;
  overflow: hidden;
}
.learning-featured .disclosure-link {
  min-height: 76px;
  padding: 20px 24px;
  border: 0;
  gap: 16px;
  font-size: 17px;
}
.feature-list {
  display: block;
  padding: 0 24px;
  background: var(--color-surface);
  border-radius: 20px;
}
.feature-link {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 16px;
  min-height: 76px;
  padding: 16px 0;
  margin: 0;
  text-align: left;
  border: 0;
  border-radius: 0;
  background: transparent;
  line-height: 1.5;
  font-size: 16px;
}
.feature-link + .feature-link {
  border-top: 1px solid var(--color-border);
}
.feature-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  flex: none;
}
.feature-copy {
  flex: 1;
  min-width: 0;
}
.feature-copy text {
  display: block;
  font-size: 17px;
  color: var(--color-text-primary);
}
.feature-arrow {
  flex: none;
}
.record-link {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  min-height: 60px;
  padding: 16px 24px;
  margin-top: 24px;
  text-align: left;
  background: var(--color-surface);
  border-radius: 20px;
  color: var(--color-text-primary);
  font-size: 16px;
}
.record-link + .record-link {
  margin-top: 12px;
}
.secondary-list {
  margin-top: 12px;
}
.secondary-list .feature-link {
  justify-content: space-between;
  min-height: 60px;
}
.feature-link:active,
.record-link:active {
  opacity: 0.65;
}
@media (hover: hover) {
  .feature-link:hover {
    color: var(--color-primary);
  }
}
.learning-heading {
  margin: 4px 0 16px;
  font-size: 18px;
  font-weight: 600;
  letter-spacing: -0.02em;
}
.learning-gateways {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 32px;
}
.learning-gateway {
  display: flex;
  align-items: center;
  gap: 16px;
  min-height: 120px;
  width: 100%;
  margin: 0;
  padding: 24px;
  border-radius: 22px;
  background: #e7f2ff;
  color: #164f83;
  text-align: left;
}
.learning-gateway.orange {
  background: #fff0da;
  color: #874b18;
}
.learning-gateway text {
  flex: 1;
  font-size: 20px;
  font-weight: 600;
}
.learning-featured {
  background: #eaf5ef;
}
@media (max-width: 520px) {
  .learning-gateway {
    flex-wrap: wrap;
    gap: 10px;
    padding: 22px;
  }
  .learning-gateway text {
    flex-basis: 100%;
    font-size: 18px;
  }
  .learning-gateway > :last-child {
    display: none;
  }
}
</style>
