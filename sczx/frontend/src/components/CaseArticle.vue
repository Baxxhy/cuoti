<script setup>
import SpeechReader from './SpeechReader.vue';
import MathVerification from './MathVerification.vue';
import { BookOpen, ExternalLink } from 'lucide-vue-next';
const props=defineProps({value:Object});
const fieldLabel = field => field === 'content' || !field ? '案例正文' : (labels[field.split('.')[0]] || field)+(field.includes('.')?' '+(Number(field.split('.')[1])+1):'');
const labels={knowledgePoints:'知识点',goal:'教学目标',studentBase:'学生基础',difficulty:'学生困难',introduction:'引入方法',steps:'讲解步骤',questions:'教师提问',responses:'可能回应',adjustment:'回应后的调整',boundary:'适用边界',suggestions:'模型建议'};
</script>
<template>
  <article v-if="value" class="case-reading-article">
    <div class="case-meta"><BookOpen :size="16" /><span>{{ value.source || '来源待补充' }}</span><span v-if="value.grade">{{ value.grade }}</span><span v-if="value.subject">{{ value.subject }}</span><span v-if="value.author">{{ value.author }}</span><span v-if="value.version">v{{ value.version }}</span></div>
    <div v-if="value.knowledgeLinks?.length" class="case-knowledge-links"><Status v-for="p in value.knowledgeLinks" :key="p.id">{{ p.name }}</Status></div><SpeechReader :text="value.title+'。'+value.content" />
    <p class="model-prose">{{ value.content }}</p>
    <section v-for="(label,key) in labels" v-show="value.experience?.[key]?.length" :key="key"><h3>{{ label }}</h3><ul v-if="Array.isArray(value.experience?.[key])"><li v-for="(text,index) in value.experience[key]" :key="index">{{ text }}</li></ul><p v-else>{{ value.experience?.[key] }}</p></section>
    <details v-if="value.references?.length" class="case-source-list" open><summary>原文依据</summary><section v-for="(item,index) in value.references" :key="index"><a :href="`/#/source?unit=${encodeURIComponent(item.unitId)}`" target="_blank" rel="noopener">{{ item.materialTitle }} · {{ item.label }}<ExternalLink :size="14" /></a><span class="reference-field">{{ fieldLabel(item.field) }}</span><blockquote>{{ item.quote }}</blockquote></section></details>
    <p v-else class="model-model-name">{{ value.legacy ? '历史案例未关联上传原文。' : '尚未关联原文。' }}</p>
    <MathVerification :value="value.verification" />
    <InfoTip v-if="value.verification" label="数学核对范围">{{ value.verification.scope }}；{{ {verified:'列出的表达式已核对',inconsistent:'发现不一致，需人工核对',unverified:'需人工核对'}[value.verification.status] }}</InfoTip>
  </article>
</template>
