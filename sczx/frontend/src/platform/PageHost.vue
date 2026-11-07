<script setup>
import {computed,provide} from 'vue'
import {pageContext} from './page-context.js'
const props=defineProps({entry:Object,active:Boolean,component:[Object,Function]})
provide(pageContext,{active:computed(()=>props.active),options:props.entry.options})
</script>
<template><div v-show="active && component" class="web-page-host"><KeepAlive><component v-if="active" :is="component" /></KeepAlive></div></template>
<style>.web-page-host {display:block;position:relative;min-height:100vh;background:var(--color-bg)}</style>
