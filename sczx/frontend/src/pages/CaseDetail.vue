<script setup>
import { computed, inject, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { modelApi } from "@/services/models.js";
import CaseArticle from "@/components/CaseArticle.vue";
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
const route = useRoute(), selectedCase = ref(null), loading = ref(false), error = ref('');
const currentCase = computed(() => route.query.caseId ? selectedCase.value : store.data.publishedCase);
let generation = 0;
watch(() => [route.query.caseId,route.query.versionId], async ([id]) => {
  const version = ++generation; selectedCase.value = null; error.value = ''; loading.value = !!id;
  if (!id) return;
  try { const item = await modelApi.caseDetail(String(id),route.query.versionId); if (version === generation) selectedCase.value = item; }
  catch (problem) { if (version === generation) error.value = problem.message; }
  finally { if (version === generation) loading.value = false; }
}, { immediate: true });
watch(
  () => store.data.favorite,
  () => store.touch(),
);
</script>
<template>
  <RouteButton v-if="route.query.interventionClass&&currentCase" :route="'insights?class='+route.query.interventionClass+'&task='+(route.query.interventionTask||'')+'&interventionCase='+currentCase.id" secondary>用于补充教学</RouteButton>
  <p v-if="loading" role="status">读取案例中…</p>
  <Surface v-else-if="error || !currentCase"><div class="empty-state"><p role="alert">{{ error || '暂无已发布的案例' }}</p><Button @click="navigate('cases')">返回教学案例</Button></div></Surface>
  <template v-else>
  <div class="back-line">
    <Button variant="ghost" @click="navigate('cases')"
      ><ArrowLeft />返回教学案例</Button
    >
  </div>
  <div class="case-detail-header">
    <div>

      <h1>{{ currentCase.title }}</h1>
    </div>
    <div class="heading-actions">
      <Button
        v-if="currentCase.id === store.data.publishedCase?.id"
        variant="outline"
        @click="
          store.data.favorite = !store.data.favorite;
          notify(store.data.favorite ? '案例已加入收藏' : '已取消收藏');
        "
        ><Star :fill="store.data.favorite ? 'currentColor' : 'none'" />{{
          store.data.favorite ? "已收藏" : "收藏案例"
        }}</Button
      ><Button
        v-if="store.user?.role === 'teacher'"
        @click="
          store.useCase(currentCase);
          navigate('prepare');
        "
        >用于备课</Button
      >
    </div>
  </div>
  <div class="case-detail-grid teacher-case-reading">
    <article class="case-article"><CaseArticle :value="currentCase" /></article>
    <aside>
      <details class="case-use-card teacher-context-card"><summary>适用情境</summary><div v-for="(label,key) in {studentBase:'学生基础',difficulty:'学生困难',goal:'教学目标',boundary:'适用边界'}" v-show="currentCase.experience?.[key]" :key="key"><span>{{ label }}</span><p>{{ currentCase.experience?.[key] }}</p></div>
        <div class="source-box">
          <BookOpen :size="16" />
          <p>
            {{ currentCase.source || '团队编写示例' }}<InfoTip label="案例出处"
              >来源按已发布案例保存。</InfoTip
            >
          </p>
        </div>
</details
      >
    </aside>
  </div>
  </template>
</template>
