<script setup>
import { computed, ref } from "vue";
import { useLearning } from "@/store.js";


import { ArrowUpRight, BookOpen, Users, Search } from "lucide-vue-next";
import { motion } from "motion-v";
const store = useLearning(),
  query = ref(""),
  tab = ref("all"),
  grade = ref("math"),
  unit = ref("equation");
const matches = computed(
  () =>
    !query.value ||
    (
      store.data.publishedCase?.title +
      store.data.publishedCase?.content +
      "等式 天平 学生 困难 变号 同时"
    ).includes(query.value),
);
</script>
<template>
  <PageHeading title="教学案例" />
  <div class="case-toolbar">
    <div class="search-field">
      <Search :size="17" /><Input
        v-model="query"
        aria-label="搜索教学案例"
        placeholder="搜索知识点、目标或学生困难"
      />
    </div>
    <AppSelect
      v-model="grade"
      label="选择学科年级"
      :options="[{ value: 'math', label: '七年级数学' }]"
    /><AppSelect
      v-model="unit"
      label="选择单元"
      :options="[{ value: 'equation', label: '一元一次方程' }]"
    />
  </div>
  <AppTabs
    v-model="tab"
    :items="[
      { value: 'all', label: '全部案例' },
      { value: 'favorite', label: '我的收藏' },
    ]"
  />
  <div
    v-if="matches && (tab === 'all' || store.data.favorite)"
    class="case-grid"
  >
    <motion.article class="featured-case" :while-hover="{ y: -3 }"
      ><div class="case-image">
        <img
          src="/images/equation-balance.png"
          alt="天平与等式教学案例封面"
        /><Status>等式性质</Status>
      </div>
      <div class="featured-case-body">
        <div class="case-meta">
          <BookOpen :size="14" /><span>团队编写案例示例</span><span>·</span
          ><span>观察与追问</span>
        </div>
        <h2>{{ store.data.publishedCase?.title || "天平与等式性质" }}</h2>
        <p>
          当学生会说“移过去变号”，却说不清为什么时，让观察、操作与解释重新连接起来。
        </p>
        <div class="case-footer">
          <span><Users :size="14" />适用初学等式性质的学生</span
          ><RouteButton route="case-detail"
            >阅读案例<ArrowUpRight
          /></RouteButton>
        </div></div
    ></motion.article>
    <aside class="case-reading-guide">
      <h2>学生困难</h2>
      <div class="case-question-links">
        <button
          v-for="item in [
            '学生只改变等式的一边',
            '学生机械记忆移项变号',
            '怎样检查学生独立理解',
          ]"
          :key="item"
          @click="query = item"
        >
          {{ item }}<ArrowUpRight :size="15" />
        </button>
      </div>
      <InfoTip label="内容来源说明"
        >公开来源与使用条件将在内容整理阶段逐项核对。当前为完整流程的自编示例。</InfoTip
      >
    </aside>
  </div>
  <Surface v-else
    ><div class="empty-state">
      <h3>暂时没有匹配的案例</h3>
      <Button
        variant="outline"
        @click="
          query = '';
          tab = 'all';
        "
        >浏览全部案例</Button
      >
    </div></Surface
  >
</template>
