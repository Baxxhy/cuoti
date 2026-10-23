<template>
  <view class="custom-tab-bar" role="navigation" aria-label="主要导航">
    <view class="nav-brand">
      <uni-icons aria-hidden="true" type="compose" size="25" color="var(--color-primary)" />
      <text>错题帮</text>
    </view>
    <view
      v-for="item in left"
      :key="item.path"
      class="tab-item"
      :class="{ active: current === item.key }"
      role="button"
      tabindex="0"
      :aria-label="item.text"
      :aria-current="current === item.key ? 'page' : undefined"
      @click="switchPage(item.path)"
      @keydown.enter="switchPage(item.path)"
    >
      <uni-icons
        aria-hidden="true"
        :type="item.icon"
        size="24"
        :color="current === item.key ? 'var(--color-primary)' : 'var(--color-text-secondary)'"
      />
      <text>{{ item.text }}</text>
    </view>
    <view
      class="tab-item tab-capture"
      :class="{ active: current === 'capture' }"
      role="button"
      tabindex="0"
      aria-label="录入错题"
      :aria-current="current === 'capture' ? 'page' : undefined"
      @click="switchPage('/pages/capture/capture')"
      @keydown.enter="switchPage('/pages/capture/capture')"
    >
      <uni-icons
        aria-hidden="true"
        type="camera-filled"
        size="24"
        :color="current === 'capture' ? 'var(--color-primary)' : 'var(--color-text-secondary)'"
      />
      <text>录入</text>
    </view>
    <view
      v-for="item in right"
      :key="item.path"
      class="tab-item"
      :class="{ active: current === item.key }"
      role="button"
      tabindex="0"
      :aria-label="item.text"
      :aria-current="current === item.key ? 'page' : undefined"
      @click="switchPage(item.path)"
      @keydown.enter="switchPage(item.path)"
    >
      <uni-icons
        aria-hidden="true"
        :type="item.icon"
        size="24"
        :color="current === item.key ? 'var(--color-primary)' : 'var(--color-text-secondary)'"
      />
      <text>{{ item.text }}</text>
    </view>
  </view>
</template>
<script setup>
import { switchSection } from '@/utils/navigation.js'
defineProps({ current: { type: String, default: 'home' } })
const left = [
  { key: 'home', text: '今日', icon: 'home', path: '/pages/index/index' },
  { key: 'problems', text: '错题', icon: 'list', path: '/pages/problem/list' },
]
const right = [
  { key: 'learning', text: '学习', icon: 'calendar', path: '/pages/learning/learning' },
  { key: 'profile', text: '我的', icon: 'person', path: '/pages/profile/profile' },
]
function switchPage(path) {
  switchSection(path)
}
</script>
<style scoped lang="scss">
.custom-tab-bar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  max-width: 960px;
  margin: 0 auto;
  min-height: 72px;
  padding: 8px 12px calc(8px + env(safe-area-inset-bottom));
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  border-top: 1px solid var(--color-border);
  z-index: 99;
}
.nav-brand {
  display: none;
}
.tab-item {
  flex: 1;
  max-width: 150px;
  min-height: 52px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  color: var(--color-text-secondary);
  font-size: 11px;
  border-radius: 12px;
  cursor: pointer;
  transition: background-color 160ms ease;
}
.tab-item.active {
  color: var(--color-primary);
  font-weight: 600;
}
.tab-item:active {
  background: var(--color-bg);
}
@media (min-width: 1100px) {
  .custom-tab-bar {
    top: 0;
    bottom: 0;
    right: auto;
    left: max(0px, calc((100vw - 1180px) / 2));
    width: 216px;
    max-width: none;
    padding: 48px 20px;
    border: 0;
    background: var(--color-bg);
    flex-direction: column;
    align-items: stretch;
    justify-content: flex-start;
    gap: 6px;
  }
  .nav-brand {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 0 14px 36px;
    color: var(--color-brand-deep);
    font-size: 21px;
    font-weight: 650;
    letter-spacing: -0.04em;
  }
  .tab-item {
    flex: none;
    max-width: none;
    min-height: 48px;
    padding: 0 16px;
    flex-direction: row;
    justify-content: flex-start;
    gap: 13px;
    font-size: 14px;
  }
  .tab-item.active {
    background: var(--color-primary-soft);
    color: var(--color-primary);
  }
  .tab-item:hover {
    background: var(--color-primary-soft-hover);
  }
}
</style>
