<template>
  <view class="page">
    <app-header title="学习" />
    <view class="page-content">
      <view class="learning-featured">
        <text class="eyebrow">从错题，到自己的方法</text>
        <text class="editorial-title">这次，解决反复卡住的地方。</text>
        <button
          aria-label="个人易错地图 找到线索，回到原题，再沿路线修复"
          role="button"
          tabindex="0"
          class="disclosure-link"
          @keydown.enter.prevent="go('/pages/error-map/error-map')"
          @keydown.space.prevent
          @keyup.space.prevent="go('/pages/error-map/error-map')"
          @click="go('/pages/error-map/error-map')"
        >
          <view>
            <text>个人易错地图</text>
            <small>找到线索，回到原题，再沿路线修复</small>
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
            <text>{{ item.description }}</text>
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
import { learningPrimaryEntries, learningRecordEntries } from '@/constants/learning.js'
import { go } from '@/utils/navigation.js'
const moreOpen = ref(false)
</script>
<style scoped lang="scss">
.learning-featured {
  margin-bottom: 28px;
  border-top: 2px solid var(--color-text-primary);
  padding-top: 20px;
}
.learning-featured .disclosure-link small {
  display: block;
  color: var(--color-text-secondary);
  font-size: 13px;
  margin-top: 6px;
}
.feature-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.feature-link {
  position: relative;
  width: 100%;
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: flex-start;
  gap: 16px;
  min-height: 164px;
  padding: 20px 16px;
  margin: 0;
  text-align: left;
  border: 1px solid var(--color-border);
  border-radius: 16px;
  background: var(--color-surface);
  line-height: 1.5;
  font-size: 16px;
}
.feature-icon {
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  background: var(--color-primary-soft);
}
.feature-arrow {
  position: absolute;
  top: 20px;
  right: 16px;
}
.feature-link::after,
.record-link::after {
  border: 0;
}
.feature-link:active {
  background: var(--color-primary-soft);
}
.feature-copy {
  flex: 1;
  min-width: 0;
  width: 100%;
  overflow-wrap: anywhere;
}
.feature-copy text {
  display: block;
  font-size: 18px;
  color: var(--color-text-primary);
}
.feature-copy text + text {
  font-size: 14px;
  margin-top: 4px;
  color: var(--color-text-secondary);
}
.record-link {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  min-height: 52px;
  padding: 12px 0;
  margin-top: 12px;
  text-align: left;
  background: transparent;
  font-size: 16px;
}
.secondary-list {
  display: block;
  margin-top: 8px;
  border: 1px solid var(--color-border);
  border-radius: 12px;
  overflow: hidden;
}
.secondary-list .feature-link {
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  min-height: 52px;
  padding: 14px 16px;
  border: 0;
  border-radius: 0;
}
.secondary-list .feature-link + .feature-link {
  border-top: 1px solid var(--color-border);
}
@media (max-width: 320px) {
  .feature-list {
    grid-template-columns: 1fr;
  }
}
</style>
