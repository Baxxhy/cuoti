<script setup>
defineProps({item:{type:Object,required:true}});
</script>
<template><details v-if="item.matchReasons?.length||item.matchedFields?.length||item.knowledgeMatches?.length" class="match-evidence"><summary>为什么匹配</summary><ul><li v-for="reason in item.matchReasons" :key="reason">{{ reason }}</li><li v-for="point in item.knowledgeMatches" :key="point.id">{{ point.name }} · {{ point.relation==='direct'?'直接关联':'一层前置' }}</li></ul><div v-for="field in item.matchedFields?.filter(f=>f.matchedTerms?.length)" :key="field.field" class="match-field"><strong>{{ field.label }}</strong><span>{{ field.matchedTerms.join('、') }}</span></div><InfoTip label="检索分值说明">分值只用于本次排序，不是相关概率或内容正确率。原文依据请进入案例查看。</InfoTip></details></template>
