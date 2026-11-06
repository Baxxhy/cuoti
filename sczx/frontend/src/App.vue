<script setup>
import { computed, defineAsyncComponent } from 'vue'
import { currentUrl, notice, parsePage, pageStack } from './platform/browser.js'
import routes from './routes.json'
import PageHost from './platform/PageHost.vue'
import WebDialogs from './platform/WebDialogs.vue'
import WebImagePreview from './platform/WebImagePreview.vue'
const modules=import.meta.glob('./pages/**/*.vue')
const pages=Object.fromEntries(routes.map(path=>[path,defineAsyncComponent(modules[`./${path}.vue`])]))
const page=computed(()=>pages[parsePage(currentUrl.value).route])
</script>
<template>
  <PageHost v-for="(entry,index) in pageStack" :key="entry.key" :entry="entry" :active="index===pageStack.length-1" :component="pages[entry.route]" />
  <main v-if="!page" class="page-content"><h1>页面不存在</h1><a href="#/pages/index/index">返回首页</a></main>
  <WebDialogs />
  <WebImagePreview />
  <div v-if="notice" class="web-toast" :class="{'web-toast-symbol':notice.icon!=='none'}">
    <WebIcon v-if="notice.icon!=='none'" type="checkmarkempty" size="55" color="#fff" class="web-toast-success-icon" />
    <span class="web-toast-text">{{notice.title}}</span>
  </div>
</template>
<style lang="scss">
@import './styles/platform-controls.scss';
@import './styles/uni-common.scss';
@font-face {font-family:SczxIcons;src:url('./platform/uniicons.ttf') format('truetype');font-display:swap}
html,body,#app {margin:0;min-height:100%;width:100%}
button {cursor:pointer;line-height:1.4}
button:disabled {cursor:default}
.web-icon {font-family:SczxIcons!important;display:inline-block;vertical-align:middle;font-style:normal}
.web-icon::before {content:attr(data-glyph)}
.web-toast {font-family:initial;color:initial;position:fixed;left:50%;top:50%;transform:translate(-50%,-50%);max-width:80%;text-align:center;line-height:normal;font-size:16px;z-index:999;pointer-events:none}
.web-toast-text {box-sizing:content-box;display:inline-block;vertical-align:middle;padding:10px 20px;border-radius:5px;font-size:13px;line-height:normal;color:#fff;background:rgba(17,17,17,.7);text-align:center;max-width:100%;word-break:break-word;white-space:normal}
.web-toast-symbol {width:8em;background:rgba(17,17,17,.7);border-radius:5px;color:#fff}
.web-toast-symbol .web-toast-success-icon {display:block;margin:15px auto 0}
.web-toast-symbol .web-toast-text {box-sizing:content-box;display:block;font-size:16px;padding:0;margin:0 0 15px;background:none}
.web-picker {position:relative}
.web-picker-control {position:absolute;inset:0;width:100%;height:100%;opacity:0;cursor:pointer}
.web-picker-control:focus {outline:none}
.web-loading {padding:18px;text-align:center;color:var(--color-text-secondary)}
</style>
