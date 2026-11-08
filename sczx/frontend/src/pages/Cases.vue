<script setup>
import { onBeforeUnmount, ref, watch } from 'vue';
import { useLearning } from '@/store.js';
import { useModelJob } from '@/lib/useModelJob.js';
import { modelApi } from '@/services/models.js';
import { navigate } from '@/lib/navigation.js';
import { ArrowUpRight, BookOpen, Search, RefreshCw } from 'lucide-vue-next';
const store = useLearning();
const query = ref(''), tab = ref('all'), items = ref([]), loading = ref(false), error = ref('');
let generation = 0, timer;
const sortWarning = ref('');
const { busy: sorting, error: sortError, create: sortCases, open } = useModelJob(value => {
  if (value.status === 'succeeded' && value.input?.query === query.value.trim()) { items.value = value.result.items; sortWarning.value = value.result.warning || ''; }
});
function semanticSort() { sortWarning.value = ''; return sortCases({ capability: 'retrieval', data: { query: query.value, rerank: true } }); }
async function load() {
  const version = ++generation; loading.value = true; error.value = '';
  try { const result = await modelApi.search(query.value); if (version === generation) items.value = result.items; }
  catch (problem) { if (version === generation) { error.value = problem.message; items.value = []; } }
  finally { if (version === generation) loading.value = false; }
}
watch(query, () => { open(null); sortWarning.value = ''; clearTimeout(timer); generation++; loading.value = true; timer = setTimeout(load, 250); }, { immediate: true });
onBeforeUnmount(() => { clearTimeout(timer); generation++; });
function read(item) { navigate('case-detail?caseId=' + encodeURIComponent(item.id)); }
</script>
<template>
  <PageHeading title="教学案例" />
  <div class="case-toolbar"><form class="search-field" @submit.prevent="load"><Search :size="17" /><Input v-model="query" aria-label="搜索教学案例" placeholder="搜索知识点或学生困难" /></form><Button variant="outline" :disabled="loading || sorting || !query.trim() || !items.length" @click="semanticSort">{{ sorting ? '排序中…' : '语义排序' }}</Button><InfoTip label="检索方式">BM25 中文检索，搜索已发布的案例标题与正文；可用 Codex 进一步语义排序。</InfoTip></div>
  <AppTabs v-model="tab" :items="[{ value: 'all', label: '全部案例' }, { value: 'favorite', label: '我的收藏' }]" />
  <p v-if="sortError || sortWarning" role="alert" class="form-error">{{ sortError || sortWarning }}</p>
  <p v-if="loading" role="status" class="ai-empty">正在检索…</p>
  <Surface v-else-if="error"><div class="empty-state"><p role="alert">{{ error }}</p><Button variant="outline" @click="load"><RefreshCw :size="16" />重试</Button></div></Surface>
  <div v-else class="case-search-layout">
    <div class="case-search-results">
      <article v-for="item in items.filter(x => tab !== 'favorite' || (store.data.favorite && x.id === store.data.publishedCase?.id))" :key="item.id" class="case-search-card">
        <div class="case-meta"><BookOpen :size="15" /><span>{{ item.source || '团队编写案例示例' }}</span></div><h2>{{ item.title }}</h2><p>{{ item.content.slice(0, 180) }}{{ item.content.length > 180 ? '…' : '' }}</p><Button variant="outline" @click="read(item)">阅读案例<ArrowUpRight :size="16" /></Button>
      </article>
      <Surface v-if="!items.length || (tab === 'favorite' && !items.some(x => store.data.favorite && x.id === store.data.publishedCase?.id))"><div class="empty-state"><h3>{{ tab === 'favorite' ? '暂无收藏的匹配案例' : '没有匹配的案例' }}</h3><Button variant="outline" @click="query = ''; tab = 'all'">浏览全部案例</Button></div></Surface>
    </div>
    <aside class="case-reading-guide"><h2>学生困难</h2><div class="case-question-links"><button v-for="item in ['学生只改变等式的一边', '学生机械记忆移项变号', '怎样检查学生独立理解']" :key="item" @click="query = item">{{ item }}<ArrowUpRight :size="15" /></button></div></aside>
  </div>
</template>
