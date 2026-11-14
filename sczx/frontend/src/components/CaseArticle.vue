<script setup>
import SpeechReader from './SpeechReader.vue';
import MathVerification from './MathVerification.vue';
import { BookOpen, ExternalLink } from '@/components/app/icons.js';
const props=defineProps({value:Object});
const fieldLabel = field => field === 'content' || !field ? '案例正文' : (labels[field.split('.')[0]] || field)+(field.includes('.')?' '+(Number(field.split('.')[1])+1):'');
const labels={knowledgePoints:'知识点',goal:'教学目标',studentBase:'学生基础',difficulty:'学生困难',diagnosis:'诊断依据',strategy:'具体教法',effectCheck:'效果检查',introduction:'引入方法',steps:'讲解步骤',questions:'教师提问',responses:'可能回应',adjustment:'回应后的调整',boundary:'适用边界',suggestions:'模型建议'};
</script>
<template>
  <Surface data-ui="card" role="article" v-if="value" class="case-reading-article">
    <Status>{{{teacher:'教师提供（需核对确认依据）',public:'公开材料整理',team:'团队自编',ai_candidate:'AI辅助候选',unknown:'来源未核验'}[value.provenance?.kind||'unknown']}}</Status><div class="case-meta"><BookOpen :size="16" /><span>{{ value.source || '来源待补充' }}</span><span v-if="value.grade">{{ value.grade }}</span><span v-if="value.subject">{{ value.subject }}</span><span v-if="value.provenance?.author||value.author">{{ value.provenance?.author||value.author }}</span><span v-if="value.version">v{{ value.version }}</span></div>
    <div v-if="value.knowledgeLinks?.length" class="case-knowledge-links"><Status v-for="p in value.knowledgeLinks" :key="p.id">{{ p.name }}</Status></div><SpeechReader :text="value.title+'。'+value.content" />
    <p class="model-prose">{{ value.content }}</p>
    <div class="teacher-case-sections"><template v-for="(label,key) in labels" :key="key"><section v-if="['goal','introduction','steps'].includes(key)&&value.experience?.[key]?.length"><h3>{{ label }}</h3><ol v-if="Array.isArray(value.experience?.[key])"><li v-for="(text,index) in value.experience[key]" :key="index">{{ text }}</li></ol><p v-else>{{ value.experience[key] }}</p></section><AppDisclosure v-else-if="value.experience?.[key]?.length"><template #title>{{ label }}</template><ul v-if="Array.isArray(value.experience?.[key])"><li v-for="(text,index) in value.experience[key]" :key="index">{{ text }}</li></ul><p v-else>{{ value.experience[key] }}</p></AppDisclosure></template></div>
    <AppDisclosure v-if="value.references?.length" class="case-source-list"><template #title>{{value.references.some(r=>r.quoteKind==='adapted_summary')?'摘要与来源':'原文依据'}}</template><section v-for="(item,index) in value.references" :key="index"><ElLink :underline="false" :href="`/#/source?unit=${encodeURIComponent(item.unitId)}`" target="_blank" rel="noopener">{{ item.materialTitle }} 　 {{ item.label }}<ExternalLink :size="14" /></ElLink><span class="reference-field">{{ fieldLabel(item.field) }}</span><blockquote>{{ item.quote }}</blockquote></section></AppDisclosure>
    <InfoTip v-else label="原文关联">{{ value.legacy ? '历史案例未关联上传原文。' : '尚未关联原文。' }}</InfoTip>
    <MathVerification :value="value.verification" />
    <InfoTip v-if="value.verification" label="数学核对范围">{{ value.verification.scope }}；{{ {verified:'列出的表达式已核对',inconsistent:'发现不一致，需人工核对',unverified:'需人工核对'}[value.verification.status] }}</InfoTip>
  </Surface>
</template>
