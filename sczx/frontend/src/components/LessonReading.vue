<script setup>
import {computed} from 'vue';
import MathExpression from './MathExpression.vue';
import {readingLines,relatedExample,readingValue} from '@/lib/lesson-reading.js';
const props=defineProps({lesson:Object,block:Object});
const text=computed(()=>readingValue(props.lesson,props.block));
const lines=computed(()=>readingLines(text.value));
const hasMath=computed(()=>lines.value.some(line=>line.parts.some(p=>p.type==='equation')));
const example=computed(()=>!hasMath.value&&props.block.type==='explanation'?relatedExample(props.lesson,props.block):null);
const unknown=computed(()=>{const variables=[...new Set(example.value?.equation.match(/[a-zA-Z]/g)||[])];return text.value.includes('未知')&&variables.length===1?variables[0]:null;});
</script>
<template><div :class="['step-reading',{'has-example':example,'worked-example':block.type==='example','reading-instruction':['practice','check','activity'].includes(block.type)}]"><div class="step-reading-copy"><div v-for="(line,index) in lines" :key="index" class="step-reading-line"><span v-if="block.type==='example'" class="worked-example-number" aria-hidden="true">{{index+1}}</span><p><template v-for="(part,n) in line.parts" :key="n"><MathExpression v-if="part.type==='equation'" :text="part.text" inline/><span v-else>{{part.text}}</span></template></p></div></div><figure v-if="example" class="step-example-equation"><figcaption>本课例题<InfoTip label="例题来源">{{example.title}}</InfoTip></figcaption><MathExpression :text="example.equation"/><span v-if="unknown" class="step-unknown"><em>{{unknown}}</em>未知数</span></figure></div></template>
