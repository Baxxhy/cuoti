<script setup>
import {computed,ref} from 'vue';
import BalanceActivity from './BalanceActivity.vue';
import LessonReading from './LessonReading.vue';
import MathExpression from './MathExpression.vue';
import {readingValue} from '@/lib/lesson-reading.js';
const props=defineProps({lesson:{type:Object,required:true},progress:{type:Object,default:()=>({})},preview:Boolean,focused:Boolean,activeBlockId:String,questionIndex:{type:Number,default:null}});
const emit=defineEmits(['progress','focus']);
const imageErrors=ref({});
const kinds={explanation:'讲解',example:'例题',activity:'互动',discussion:'思考与表达',practice:'随堂练习',check:'独立练习'};
const blocks=computed(()=>props.focused?(props.lesson.blocks||[]).filter(b=>b.id===(props.activeBlockId||props.lesson.blocks?.[0]?.id)):props.lesson.blocks||[]);
const questions=computed(()=>props.lesson.questions||[]);
function blockQuestions(block){const list=questions.value.map((q,index)=>({...q,index})).filter(q=>block.questionIds?.includes(q.id));return props.focused?[list.find(q=>q.index===props.questionIndex)||list[0]].filter(Boolean):list}
function update(block,patch){emit('progress',block.id,{...props.progress[block.id],...patch})}
</script>
<template>
 <article :class="['curriculum-reading',{'focused-reading':focused}]">
  <div v-if="!focused" class="curriculum-reading-intro"><h2 v-if="preview">{{lesson.title}}</h2><AppDisclosure><template #title>学习目标</template><p>{{lesson.goal}}</p></AppDisclosure></div>
  <section v-for="block in blocks" :key="block.id" class="curriculum-block" :data-block="block.id" @click="emit('focus',block.id)">
   <div class="curriculum-block-heading"><h2 tabindex="-1">{{readingValue(lesson,block,'title')}}</h2><Status v-if="!focused">{{kinds[block.type]||'历史内容'}}</Status></div>
   <LessonReading :lesson="lesson" :block="block"/>
   <figure v-if="block.imageUrl" class="curriculum-figure"><AppAlert type="error" v-if="imageErrors[block.id]" role="alert" class="form-error">图片无法读取<AppButton variant="ghost" @click="imageErrors[block.id]=false">重试图片</AppButton></AppAlert><AppImage v-else :src="block.imageUrl+'?inline=1'" :alt="block.imageAlt||block.title" @error="imageErrors[block.id]=true"/></figure>
   <BalanceActivity v-if="block.type==='activity'&&['balance','equality_operations'].includes(block.activity?.type)" :config="block.activity" :state="progress[block.id]?.visualization||null" :model-value="progress[block.id]?.weight||0" @change="update(block,{visualization:$event,weight:$event.state.left===$event.state.right?$event.actions.length:0,completed:false})"/>
   <AppAlert type="error" v-else-if="block.type==='activity'" class="form-error">该互动暂不支持，请联系教师。</AppAlert>
   <template v-if="block.type==='activity'||block.type==='discussion'"><label :for="'explain-'+block.id" class="field-label">你观察到了什么？</label><Textarea :id="'explain-'+block.id" :model-value="progress[block.id]?.explanation||''" @update:model-value="update(block,{explanation:$event,completed:false})"/></template>
   <template v-if="block.type==='practice'||(block.type==='check'&&!focused)"><div v-for="q in blockQuestions(block)" :key="q.id" class="curriculum-question-preview"><strong>{{q.prompt}}</strong><MathExpression v-if="q.equation" :text="q.equation"/><slot name="question" :question="q" :index="q.index" :block="block"><p v-if="preview" class="muted">{{block.type==='practice'?'随堂练习':'独立练习'}}</p></slot></div></template>
   <p v-if="focused&&block.type==='check'" class="step-check-count">{{questions.filter(q=>q.kind!=='practice').length}} 道题</p>
   <AppButton v-if="!focused&&!['practice','check'].includes(block.type)" variant="outline" size="sm" :disabled="block.type==='activity'&&(!(progress[block.id]?.weight>0)||!progress[block.id]?.explanation?.trim())" @click="update(block,{completed:!progress[block.id]?.completed})">{{progress[block.id]?.completed?'已完成':'标记完成'}}</AppButton>
  </section>
 </article>
</template>
