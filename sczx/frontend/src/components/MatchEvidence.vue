<script setup>
defineProps({item:{type:Object,required:true}});
</script>
<template><AppDisclosure v-if="item.matchReasons?.length||item.matchedFields?.length||item.knowledgeMatches?.length" class="match-evidence"><template #title>匹配依据</template><ul><li v-for="reason in item.matchReasons" :key="reason">{{ reason }}</li><li v-for="point in item.knowledgeMatches" :key="point.id">{{ point.name }} 　 {{ point.relation==='direct'?'直接关联':'一层前置' }}</li></ul><Surface data-ui="card" v-for="field in item.matchedFields?.filter(f=>f.matchedTerms?.length)" :key="field.field" class="match-field"><strong>{{ field.label }}</strong><span>{{ field.matchedTerms.join('、') }}</span></Surface><InfoTip label="检索分值说明">分值只用于本次排序，不是相关概率或内容正确率。原文依据请进入案例查看。</InfoTip></AppDisclosure></template>
