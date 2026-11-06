<script setup>
import { computed, defineAsyncComponent } from 'vue'
import { currentUrl, notice, parsePage } from './platform/browser.js'
import routes from './routes.json'
const modules=import.meta.glob('./pages/**/*.vue')
const pages=Object.fromEntries(routes.map(path=>[path,defineAsyncComponent(modules[`./${path}.vue`])]))
const page=computed(()=>pages[parsePage(currentUrl.value).route])
</script>
<template>
  <component v-if="page" :is="page" :key="currentUrl" />
  <main v-else class="page-content"><h1>页面不存在</h1><a href="#/pages/index/index">返回首页</a></main>
  <div v-if="notice" class="web-toast" role="alert">{{notice}}</div>
</template>
<style lang="scss">
@import './styles/uni-common.scss';
@font-face {font-family:SczxIcons;src:url('./platform/uniicons.ttf') format('truetype');font-display:swap}
html,body,#app {margin:0;min-height:100%;width:100%}
body {font-family:-apple-system,BlinkMacSystemFont,'Microsoft YaHei',sans-serif;background:var(--color-bg);color:var(--color-text-primary)}
button,input,textarea,select {font:inherit;box-sizing:border-box}
button {cursor:pointer;line-height:1.4}
button:disabled {cursor:default}
.web-icon {font-family:SczxIcons!important;display:inline-block;line-height:1;vertical-align:middle;font-style:normal}
.web-toast {position:fixed;left:50%;bottom:90px;transform:translateX(-50%);max-width:85vw;padding:12px 20px;background:#252a34;color:white;border-radius:8px;z-index:10000}
.web-picker {position:relative}
.web-picker-control {position:absolute;inset:0;width:100%;height:100%;opacity:0;cursor:pointer}
.web-loading {padding:18px;text-align:center;color:var(--color-text-secondary)}
</style>
