<script setup>
import {computed,provide} from 'vue'
import {pageContext} from './page-context.js'
const props=defineProps({entry:Object,active:Boolean,component:[Object,Function]})
provide(pageContext,{active:computed(()=>props.active),options:props.entry.options})
</script>
<template><div class="web-page-host"><KeepAlive><component v-if="active" :is="component" /></KeepAlive></div></template>
<style>.web-page-host {display:contents}</style>
