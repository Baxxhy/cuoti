<script setup>
import { inject, watch } from "vue";
import { useLearning } from "@/store.js";
import { navigate } from "@/lib/navigation.js";

import {
  ArrowLeft,
  BookOpen,
  Sparkles,
  Eye,
  Star,
  FileText,
} from "lucide-vue-next";
const store = useLearning(),
  notify = inject("notify");
watch(
  () => store.data.favorite,
  () => store.touch(),
);
</script>
<template>
  <div class="back-line">
    <Button variant="ghost" @click="navigate('cases')"
      ><ArrowLeft />返回教学案例</Button
    >
  </div>
  <div class="case-detail-header">
    <div>
      <Status tone="blue">等式性质 · 案例示例</Status>
      <h1>{{ store.data.publishedCase?.title || "天平与等式性质" }}</h1>
    </div>
    <div class="heading-actions">
      <Button
        variant="outline"
        @click="
          store.data.favorite = !store.data.favorite;
          notify(store.data.favorite ? '案例已加入收藏' : '已取消收藏');
        "
        ><Star :fill="store.data.favorite ? 'currentColor' : 'none'" />{{
          store.data.favorite ? "已收藏" : "收藏案例"
        }}</Button
      ><Button
        @click="
          store.useCase();
          navigate('prepare');
        "
        >用于备课</Button
      >
    </div>
  </div>
  <div class="case-detail-grid">
    <article class="case-article">
      <section v-if="store.data.publishedCase" class="case-article-section">
        <div>
          <h2>发布的教学经验</h2>
          <p class="preserve-lines">{{ store.data.publishedCase.content }}</p>
        </div>
      </section>
      <div class="case-article-section">
        <span class="article-marker"><Eye :size="19" /></span>
        <div>
          <h2>预测与操作</h2>
          <p>
            展示两边相等的天平，请学生预测两边同时加入相同数量的砝码后，平衡会不会改变。让学生先表达自己的理由，再动手验证。
          </p>
          <blockquote>
            “如果只在左边加一个，它还会平衡吗？你为什么这样想？”
          </blockquote>
        </div>
      </div>
      <div class="case-article-section">
        <span class="article-marker"><FileText :size="19" /></span>
        <div>
          <h2>用等式表达</h2>
          <p>
            记录两边共同变化的完整步骤，让学生说出“同时”和“相同”分别意味着什么。再用只改变一边的例子进行对照。
          </p>
          <div class="article-equation">a = b <span>⇒</span> a + c = b + c</div>
        </div>
      </div>
      <div class="case-article-section">
        <span class="article-marker"><Sparkles :size="19" /></span>
        <div>
          <h2>根据回应调整</h2>
          <p>
            当学生只说“移项变号”时，请其写出两边同时减去同一个数的过程。学生能够解释后，再改变数字给出新题，观察能否独立完成。
          </p>
        </div>
      </div>
    </article>
    <aside>
      <Surface class="case-use-card"
        ><h3>这篇案例适合什么时候？</h3>
        <div>
          <span>学习基础</span>
          <p>理解相等关系，掌握加减法</p>
        </div>
        <div>
          <span>常见困难</span>
          <p>只改变一边，机械记忆变号</p>
        </div>
        <div>
          <span>教学目标</span>
          <p>解释共同变化，独立应用等式性质</p>
        </div>
        <div class="source-box">
          <BookOpen :size="16" />
          <p>
            团队编写示例<InfoTip label="案例出处"
              >当前案例为团队编写示例，真实来源将在内容建设阶段补充。</InfoTip
            >
          </p>
        </div>
        <Button
          @click="
            store.useCase();
            navigate('prepare');
          "
          >带入我的教案</Button
        ></Surface
      >
    </aside>
  </div>
</template>
