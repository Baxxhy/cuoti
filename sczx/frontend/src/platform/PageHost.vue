<script setup>
import {computed,provide} from 'vue'
import {pageContext} from './page-context.js'
const props=defineProps({entry:Object,active:Boolean,component:[Object,Function]})
provide(pageContext,{active:computed(()=>props.active),options:props.entry.options})
</script>
<template><div v-show="active" class="web-page-host"><component :is="component" /></div></template>
<style>.web-page-host {display:contents}</style>
