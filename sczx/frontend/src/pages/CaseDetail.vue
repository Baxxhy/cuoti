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
} from "@/components/app/icons.js";
const store = useLearning(),
  notify = inject("notify");
const route = useRoute(), selectedCase = ref(null), loading = ref(false), error = ref('');
const currentCase = computed(() => route.query.caseId ? selectedCase.value : store.data.publishedCase);
const bookmarkBusy=ref(false),bookmarkError=ref('');
const favorite=computed(()=>(store.data.favoriteCaseIds||[]).includes(currentCase.value?.id));
async function toggleFavorite(){if(bookmarkBusy.value)return;bookmarkBusy.value=true;bookmarkError.value='';const selected=!favorite.value;try{if(await store.setCaseFavorite(currentCase.value.id,selected))notify(selected?'案例已加入收藏':'已取消收藏')}catch(e){bookmarkError.value=e.message}finally{bookmarkBusy.value=false}}
let generation = 0;
watch(() => [route.query.caseId,route.query.versionId], async ([id]) => {
  const version = ++generation; selectedCase.value = null; error.value = ''; loading.value = !!id;
  if (!id) return;
  try { const item = await modelApi.caseDetail(String(id),route.query.versionId); if (version === generation) selectedCase.value = item; }
  catch (problem) { if (version === generation) error.value = problem.message; }
  finally { if (version === generation) loading.value = false; }
}, { immediate: true });
</script>
<template>
  <RouteButton v-if="route.query.interventionClass&&currentCase" :route="'insights?class='+route.query.interventionClass+'&task='+(route.query.interventionTask||'')+'&interventionCase='+currentCase.id" secondary>用于补充教学</RouteButton>
  <ElSkeleton v-if="loading" animated :rows="3" aria-label="读取案例中…"/>
  <Surface v-else-if="error || !currentCase"><AppEmpty class="empty-state"><AppAlert type="error" role="alert">{{ error || '暂无已发布的案例' }}</AppAlert><AppButton @click="navigate('cases')">返回教学案例</AppButton></AppEmpty></Surface>
  <template v-else>
  <div class="back-line">
    <AppButton variant="ghost" @click="navigate('cases')"
      ><ArrowLeft />返回教学案例</AppButton
    >
  </div>
  <div class="case-detail-header">
    <div>

      <h1>{{ currentCase.title }}</h1>
    </div>
    <div class="heading-actions">
      <AppButton
        v-if="store.user?.role==='teacher'"
        variant="outline"
        :disabled="bookmarkBusy"
        @click="toggleFavorite"
        ><Star :fill="favorite ? 'currentColor' : 'none'" />{{
          favorite ? "已收藏" : "收藏案例"
        }}</AppButton
      ><AppButton
        v-if="store.user?.role === 'teacher'"
        @click="
          navigate('agent?caseId='+encodeURIComponent(currentCase.id)+'&caseVersionId='+encodeURIComponent(currentCase.versionId));
        "
        >用于备课</AppButton
      >
    </div>
  </div>
  <AppAlert type="error" v-if="bookmarkError" class="form-error" role="alert">{{bookmarkError}}</AppAlert>
  <div class="case-detail-grid teacher-case-reading">
    <Surface data-ui="card" role="article" class="case-article"><CaseArticle :value="currentCase" /></Surface>
    <aside>
      <AppDisclosure class="case-use-card teacher-context-card"><template #title>适用情境</template><div v-for="(label,key) in {studentBase:'学生基础',difficulty:'学生困难',goal:'教学目标',boundary:'适用边界'}" v-show="currentCase.experience?.[key]" :key="key"><span>{{ label }}</span><p>{{ currentCase.experience?.[key] }}</p></div>
        <Surface data-ui="card" class="source-box">
          <BookOpen :size="16" />
          <p>
            {{ currentCase.source || '团队编写示例' }}<InfoTip label="案例出处"
              >来源按已发布案例保存。</InfoTip
            >
          </p>
        </Surface>
</AppDisclosure>
    </aside>
  </div>
  </template>
</template>
