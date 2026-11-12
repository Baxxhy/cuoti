<script setup>
import {computed} from 'vue';
import {ElDialog} from 'element-plus';
const props=defineProps({title:String,description:String,contentClass:String,width:[String,Number]});
const dialogWidth=computed(()=>props.width||(/library-preview|lesson-preview|student-detail|wrong-capture|exam-question/.test(props.contentClass||'')?'1000px':/student-tool|teacher-question-picker/.test(props.contentClass||'')?'820px':'640px'));
const open=defineModel('open',{default:false});
</script>
<template><ElDialog v-if="open" v-model="open" :title="title" :class="['app-element-dialog',contentClass]" :width="dialogWidth" align-center append-to-body destroy-on-close :close-on-click-modal="false" :aria-label="title"><p v-if="description" class="el-dialog-description">{{description}}</p><slot/></ElDialog></template>
