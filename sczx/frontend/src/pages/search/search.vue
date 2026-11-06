<template>
  <div class="page">
    <app-header title="搜索错题" back />
    <state-panel state="loading" />
  </div>
</template>
<script setup>
import { browser } from '@/platform/browser.js'
import { onLoad } from '@/platform/lifecycle.js'
import { scopedQuestionURL } from '@/utils/learning.js'
onLoad((q) =>
  browser.redirectTo({
    url: scopedQuestionURL({ subject: q.subject || '', search: q.search || q.q || '' }),
  }),
)
</script>
